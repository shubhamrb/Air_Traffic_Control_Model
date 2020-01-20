from PyQt5.QtWidgets import QWidget, QMessageBox
from ui.launcher import Ui_launcher

from session.config import settings, default_map_range_AD, default_map_range_CTR, version_string, app_icon_path
from session.env import env

from data.util import some
from data.coords import EarthCoords
from data.nav import world_navpoint_db, Navpoint, NavpointError
from data.radar import Radar
from data.comms import RadioDirectionFinder
from data.params import Heading

from models.FPLs import FlightPlanModel
from models.ATCs import AtcTableModel
from models.liveStrips import LiveStripModel
from models.discardedStrips import DiscardedStripModel
from models.cpdlc import CpdlcHistoryModel

from ext.noaa import get_declination
from ext.xplane import get_airport_data, get_frequencies, import_ILS_capabilities
from ext.resources import read_bg_img, read_point_spec, get_ground_elevation_map, load_local_navpoint_speech_data

from gui.main import MainWindow


# ---------- Constants ----------

min_map_range = 20
max_map_range = 1000

point_spec_help_message = 'Valid point specifications:' \
	'\n - decimal coordinates, e.g. 35.8765,-90.567' \
	'\n - deg-min-sec coordinate format, e.g. 48°51\'24\'\'N,2°21\'03\'\'E' \
	'\n - named point, e.g. LANUX' \
	'\n\nAdditional operators:' \
	'\n - displacement: point>radial,distance' \
	'\n - disambiguation ("nearest to"): point~refpoint' \
	'\n\nFor more detail, refer to "point specification" in the quick reference.'

# -------------------------------



def valid_location_code(code):
	return code.isalnum()



class ATCpieLauncher(QWidget, Ui_launcher):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.mapRange_edit.setMinimum(min_map_range)
		self.mapRange_edit.setMaximum(max_map_range)
		self.logo_widget.setStyleSheet('border-image: url(%s) 0 0 0 0 stretch stretch' % app_icon_path)
		self.version_info.setText('Version: %s' % version_string)
		self.last_selected_ICAO = None
		self.updateCtrLocationsList()
		self.ctrLocationCode_edit.lineEdit().textChanged.connect(self.updateStartButton)
		self.ctrLocationCode_edit.activated.connect(self.selectListedCtrLocation)
		self.AD_radioButton.toggled.connect(self.switchMode)
		self.airport_select.recognised.connect(self.recogniseAD)
		self.airport_select.unrecognised.connect(self.unrecogniseAD)
		self.airport_select.airport_edit.returnPressed.connect(self.start_button.click)
		self.radarPosHelp_button.clicked.connect(self.showRadarPosHelp)
		self.start_button.clicked.connect(self.launchWithWindowInput)
		self.exit_button.clicked.connect(self.close)
		self.AD_radioButton.setChecked(True)
	
	def switchMode(self, ad_mode):
		self.mapRange_edit.setValue(default_map_range_AD if ad_mode else default_map_range_CTR)
		self.updateStartButton()
	
	def selectListedCtrLocation(self, index):
		self.ctrRadarPos_edit.setText(settings.CTR_radar_positions[self.ctrLocationCode_edit.itemText(index)])
	
	def updateStartButton(self):
		if self.AD_radioButton.isChecked():
			self.start_button.setEnabled(self.last_selected_ICAO != None)
		else:
			self.start_button.setEnabled(valid_location_code(self.ctrLocationCode_edit.currentText()))
	
	def updateCtrLocationsList(self):
		self.ctrLocationCode_edit.clear()
		self.ctrLocationCode_edit.addItems(sorted(settings.CTR_radar_positions.keys()))
		self.ctrLocationCode_edit.clearEditText()
	
	def recogniseAD(self, ad):
		self.last_selected_ICAO = ad.code
		self.selectedAD_info.setText(ad.long_name)
		self.start_button.setEnabled(True)
	
	def unrecogniseAD(self):
		self.last_selected_ICAO = None
		self.selectedAD_info.clear()
		self.start_button.setEnabled(False)
	
	def showRadarPosHelp(self):
		QMessageBox.information(self, 'Help on point specification', point_spec_help_message)
	
	def launchWithWindowInput(self):
		self.close()
		try:
			if self.AD_radioButton.isChecked(): # Airport mode
				self.launch(self.last_selected_ICAO, mapRange=self.mapRange_edit.value())
			else: # CTR mode
				self.launch(self.ctrLocationCode_edit.currentText(), ctrPos=self.ctrRadarPos_edit.text(), mapRange=self.mapRange_edit.value())
		except ValueError as err:
			QMessageBox.critical(self, 'Start-up error', str(err))
			self.show()
	
	def launch(self, location_code, mapRange=None, ctrPos=None):
		'''
		Raise ValueError with error message if launch fails.
		'''
		settings.map_range = some(mapRange, (default_map_range_AD if ctrPos == None else default_map_range_CTR))
		print('Setting up session %s in %s mode at location %s...' % \
				(settings.sessionID(), ('AD' if ctrPos == None else 'CTR'), location_code))
		try:
			if ctrPos == None: # Airport mode
				env.airport_data = get_airport_data(location_code)
				import_ILS_capabilities(env.airport_data)
				EarthCoords.setRadarPos(env.airport_data.navpoint.coordinates)
				env.frequencies = get_frequencies(env.airport_data.navpoint.code)
				try:
					settings.restoreLocalSettings_AD(env.airport_data)
					settings.first_time_at_location = False
				except FileNotFoundError:
					print('No airport settings file found; using defaults.')
					settings.primary_METAR_station = location_code # guess on first run; AD may have a weather station
				try:
					env.elevation_map = get_ground_elevation_map(location_code)
					print('Loaded ground elevation map.')
				except FileNotFoundError:
					print('No elevation map found; using field elevation.')
			else: # CTR mode
				radar_position = read_point_spec(ctrPos, world_navpoint_db)
				EarthCoords.setRadarPos(radar_position)
				env.frequencies = []
				try:
					settings.restoreLocalSettings_CTR(location_code)
					settings.first_time_at_location = False
				except FileNotFoundError:
					print('No CTR settings file found; using defaults.')
				try:
					if settings.CTR_radar_positions[location_code] != ctrPos:
						print('Overriding previously saved radar position.')
				except KeyError:
					print('Creating new CTR position.')
				settings.CTR_radar_positions[location_code] = ctrPos
				self.updateCtrLocationsList()
		except NavpointError as err:
			raise ValueError('Navpoint error: %s' % err)
		else:
			print('Radar position is: %s' % env.radarPos())
			Heading.declination = get_declination(env.radarPos())
			env.navpoints = world_navpoint_db.subDB(lambda p: env.pointOnMap(p.coordinates))
			env.radar = Radar(self) # CAUTION: uses airport data; make sure it is already in env
			env.rdf = RadioDirectionFinder(env.radarPos())
			env.cpdlc = CpdlcHistoryModel(self)
			env.strips = LiveStripModel(self)
			env.FPLs = FlightPlanModel(self)
			env.ATCs = AtcTableModel(self)
			env.discarded_strips = DiscardedStripModel(self)
			try:
				settings.restoreGeneralAndSystemSettings()
			except FileNotFoundError:
				print('No general settings file found; using defaults.')
			settings.radar_background_images, settings.loose_strip_bay_backgrounds = read_bg_img(location_code, env.navpoints)
			load_local_navpoint_speech_data(location_code)
			session_window = MainWindow(self)
			session_window.show()
			if settings.first_time_at_location:
				title = 'New %s location' % ('radar centre' if env.airport_data == None else 'airport')
				msg = 'This is your first time at %s.\nPlease configure location settings.' % location_code
				QMessageBox.information(session_window, title, msg)
				session_window.openLocalSettings()



