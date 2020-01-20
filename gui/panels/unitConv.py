from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from ui.unitConv import Ui_unitConversionWidget
from gui.misc import IconFile, signals, selection

from data.coords import m2NM, m2ft, m2mi
from data.weather import hPa2inHg, tempC2F, tempF2C

from session.config import settings
from session.env import env


# ---------- Constants ----------


# -------------------------------


class UnitConversionWindow(QWidget, Ui_unitConversionWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.setWindowIcon(QIcon(IconFile.panel_unitConv))
		self.horizDist_km_edit.setMaximum(self.horizDist_NM_edit.maximum() / m2NM / 1000)
		self.horizDist_mi_edit.setMaximum(self.horizDist_NM_edit.maximum() / m2NM * m2mi)
		self.alt_m_edit.setMaximum(self.alt_ft_edit.maximum() / m2ft)
		self.speed_kmh_edit.setMaximum(self.speed_kt_edit.maximum() / m2NM / 1000)
		self.speed_mph_edit.setMaximum(self.speed_kt_edit.maximum() / m2NM * m2mi)
		self.speed_mps_edit.setMaximum(self.speed_kt_edit.maximum() / m2NM / 3600)
		self.temp_F_edit.setMinimum(tempC2F(self.temp_C_edit.minimum()))
		self.temp_F_edit.setMaximum(tempC2F(self.temp_C_edit.maximum()))
		self.pressure_inHg_edit.setMinimum(hPa2inHg * self.pressure_hPa_edit.minimum())
		self.pressure_inHg_edit.setMaximum(hPa2inHg * self.pressure_hPa_edit.maximum())
		self.horizDist_NM_edit.valueChanged.connect(lambda v: self.updateHorizDist(v, nm=False))
		self.horizDist_km_edit.valueChanged.connect(lambda v: self.updateHorizDist(m2NM * 1000 * v, km=False))
		self.horizDist_mi_edit.valueChanged.connect(lambda v: self.updateHorizDist(m2NM / m2mi * v, mi=False))
		self.alt_ft_edit.valueChanged.connect(lambda v: self.updateAlt(v, ft=False))
		self.alt_m_edit.valueChanged.connect(lambda v: self.updateAlt(m2ft * v, m=False))
		self.speed_kt_edit.valueChanged.connect(lambda v: self.updateSpeed(v, kt=False))
		self.speed_kmh_edit.valueChanged.connect(lambda v: self.updateSpeed(m2NM * 1000 * v, kmh=False))
		self.speed_mph_edit.valueChanged.connect(lambda v: self.updateSpeed(m2NM / m2mi * v, mph=False))
		self.speed_mps_edit.valueChanged.connect(lambda v: self.updateSpeed(m2NM * 3600 * v, mps=False))
		self.temp_C_edit.valueChanged.connect(lambda v: self.updateTemperature(v, celsius=False))
		self.temp_F_edit.valueChanged.connect(lambda v: self.updateTemperature(tempF2C(v), fahrenheit=False))
		self.pressure_hPa_edit.valueChanged.connect(lambda v: self.updatePressure(v, hPa=False))
		self.pressure_inHg_edit.valueChanged.connect(lambda v: self.updatePressure(v / hPa2inHg, inHg=False))
		self.react_to_value_changes = True
		self.updateHorizDist(100)
		self.updateAlt(100)
		self.updateSpeed(100)
		self.updateTemperature(15)
		self.updatePressure(1013.25)
		signals.selectionChanged.connect(self.syncWithSelection)
		signals.newWeather.connect(self.syncWithWeather)
		signals.hdgDistMeasured.connect(lambda hdg, dist: self.updateHorizDist(dist))
	
	def syncWithSelection(self):
		acft = selection.acft
		if acft != None:
			alt = acft.xpdrAlt()
			if alt != None:
				amsl = alt.ftAMSL(env.QNH())
				self.updateAlt(amsl if amsl <= env.transitionAltitude() else alt.ft1013())
			spd = acft.groundSpeed()
			if spd != None:
				self.updateSpeed(spd.kt)
	
	def syncWithWeather(self, station, weather):
		if station == settings.primary_METAR_station:
			vis_metres, ignore = weather.prevailingVisibility() # always returns pair
			if vis_metres != None:
				self.updateHorizDist(m2NM * vis_metres)
			wind = weather.mainWind() # if not None: whdg, wspd, gusts, unit
			if wind != None:
				if wind[3] == 'kt':
					self.updateSpeed(wind[1])
				elif wind[3] == 'm/s':
					self.updateSpeed(m2NM * 3600 * wind[1])
			temps = weather.temperatures() # if not None: temperature, dew point
			if temps != None:
				self.updateTemperature(temps[0])
			qnh = weather.QNH()
			if qnh != None:
				self.updatePressure(qnh)
	
	def updateHorizDist(self, new_nm, nm=True, km=True, mi=True):
		if self.react_to_value_changes:
			self.react_to_value_changes = False
			if nm:
				self.horizDist_NM_edit.setValue(new_nm)
			if km:
				self.horizDist_km_edit.setValue(new_nm / m2NM / 1000)
			if mi:
				self.horizDist_mi_edit.setValue(new_nm / m2NM * m2mi)
			self.react_to_value_changes = True
	
	def updateAlt(self, new_ft, ft=True, m=True):
		if self.react_to_value_changes:
			self.react_to_value_changes = False
			if ft:
				self.alt_ft_edit.setValue(new_ft)
			if m:
				self.alt_m_edit.setValue(new_ft / m2ft)
			self.react_to_value_changes = True
	
	def updateSpeed(self, new_kt, kt=True, kmh=True, mph=True, mps=True):
		if self.react_to_value_changes:
			self.react_to_value_changes = False
			if kt:
				self.speed_kt_edit.setValue(new_kt)
			if kmh:
				self.speed_kmh_edit.setValue(new_kt / m2NM / 1000)
			if mph:
				self.speed_mph_edit.setValue(new_kt / m2NM * m2mi)
			if mps:
				self.speed_mps_edit.setValue(new_kt / m2NM / 3600)
			self.react_to_value_changes = True
	
	def updateTemperature(self, new_celsius, celsius=True, fahrenheit=True):
		if self.react_to_value_changes:
			self.react_to_value_changes = False
			if celsius:
				self.temp_C_edit.setValue(new_celsius)
			if fahrenheit:
				self.temp_F_edit.setValue(tempC2F(new_celsius))
			self.react_to_value_changes = True
	
	def updatePressure(self, new_hPa, hPa=True, inHg=True):
		if self.react_to_value_changes:
			self.react_to_value_changes = False
			if hPa:
				self.pressure_hPa_edit.setValue(new_hPa)
			if inHg:
				self.pressure_inHg_edit.setValue(hPa2inHg * new_hPa)
			self.react_to_value_changes = True


