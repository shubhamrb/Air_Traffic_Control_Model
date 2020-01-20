
from PyQt5.QtWidgets import QWidget, QInputDialog
from ui.weather import Ui_weatherPane

from session.config import settings
from session.env import env
from data.weather import Weather, hPa2inHg
from gui.misc import signals
from gui.widgets.miscWidgets import WeatherDispWidget


# ---------- Constants ----------


# -------------------------------



class WeatherPane(QWidget, Ui_weatherPane):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.selectedStationWeather_groupBox.setTitle(settings.primary_METAR_station)
		for station in settings.additional_METAR_stations:
			self.additionalStations_tabs.addTab(WeatherDispWidget(), station)
		self.checkNow_button.clicked.connect(signals.weatherUpdateRequest.emit)
		self.setPrimaryStation_button.clicked.connect(self.choosePrimaryStation)
		self.addStation_button.clicked.connect(self.addWeatherStationTab)
		self.additionalStations_tabs.tabCloseRequested.connect(self.removeWeatherStationTab)
		signals.localSettingsChanged.connect(self.updateLocalAnalysis) # in case transition alt. changed
		signals.newWeather.connect(self.updateWeatherDispFromNewInfo)
		signals.sessionStarted.connect(self.updateDisplays)
		signals.sessionStarted.connect(lambda: self.checkNow_button.setEnabled(True))
		signals.sessionEnded.connect(lambda: self.checkNow_button.setEnabled(False))
	
	def updateDisplays(self):
		self.selectedStationWeather_groupBox.setTitle(settings.primary_METAR_station)
		self.selectedStation_widget.updateDisp(env.primaryWeather())
		self.updateLocalAnalysis()
		for i, ams in enumerate(settings.additional_METAR_stations):
			self.additionalStations_tabs.widget(i).updateDisp(settings.session_manager.getWeather(ams))
	
	def updateWeatherDispFromNewInfo(self, station, weather):
		if station == settings.primary_METAR_station:
			self.selectedStation_widget.updateDisp(weather)
			self.updateLocalAnalysis()
		for i, ams in enumerate(settings.additional_METAR_stations):
			if ams == station:
				self.additionalStations_tabs.widget(i).updateDisp(weather)
	
	def updateLocalAnalysis(self):
		qnh = env.QNH(noneSafe=False)
		if qnh == None:
			self.transitionLevel_info.setText('N/A')
			self.QFE_info.setText('N/A')
		else:
			self.transitionLevel_info.setText('FL%03d' % env.transitionLevel())
			if env.airport_data == None:
				self.QFE_info.setText('N/A')
			else:
				qfe = env.QFE(qnh)
				self.QFE_info.setText('%d hPa, %.2f inHg' % (qfe, hPa2inHg * qfe))
		w = env.primaryWeather()
		main_wind = None if w == None else w.mainWind()
		if env.airport_data == None or main_wind == None: # no runways or wind info
			self.rwyPref_info.setText('N/A')
		elif main_wind[0] == None: # no predominant heading
				self.rwyPref_info.setText('any')
		else:
			difflst = [(rwy.name, abs(env.RWD(rwy.orientation().opposite()))) for rwy in env.airport_data.allRunways()]
			preflst = sorted([pair for pair in difflst if pair[1] <= 90], key=(lambda pair: pair[1]))
			self.rwyPref_info.setText(', '.join(pair[0] for pair in preflst))
	
	def choosePrimaryStation(self):
		station, ok = QInputDialog.getText(self, 'Primary weather station', 'Station name:', text=settings.primary_METAR_station)
		if ok:
			settings.primary_METAR_station = station
			self.updateDisplays()
	
	def addWeatherStationTab(self):
		station, ok = QInputDialog.getText(self, 'Add a weather station', 'Station name:')
		if ok:
			station = station.upper()
			try:
				index = settings.additional_METAR_stations.index(station)
			except ValueError:
				tab = WeatherDispWidget()
				tab.updateDisp(settings.session_manager.getWeather(station))
				index = self.additionalStations_tabs.addTab(tab, station)
				settings.additional_METAR_stations.append(station)
			self.additionalStations_tabs.setCurrentIndex(index)
	
	def removeWeatherStationTab(self, index):
		if 0 <= index < self.additionalStations_tabs.count():
			self.additionalStations_tabs.removeTab(index)
			del settings.additional_METAR_stations[index]
	
