from os import path

from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5.QtWidgets import QMainWindow, QInputDialog, QFileDialog, QMessageBox, QLabel, QMenu, QAction, QActionGroup

from ui.mainWindow import Ui_mainWindow

from models.liveStrips import default_rack_name
from models.discardedStrips import ShelfFilterModel

from data.coords import EarthCoords
from data.fpl import FPL
from data.utc import timestr
from data.weather import hPa2inHg, mkWeather
from data.nav import world_routing_db
from data.strip import soft_link_detail

from session.config import settings
from session.env import env
from session.manager import SessionManager, SessionType
from session.flightGearMP import FlightGearMultiPlayerSessionManager
from session.teacher import TeacherSessionManager
from session.student import StudentSessionManager
from session.solo import SoloSessionManager_AD, SoloSessionManager_CTR

from ext.resources import read_bg_img, read_route_presets, import_entry_exit_data
from ext.sct import extract_sector
from ext.fgfs import FlightGearTowerViewer
from ext.sr import speech_recognition_available, prepare_SR_language_files, cleanup_SR_language_files

from gui.misc import Ticker, IconFile, signals, selection
from gui.actions import new_strip_dialog, edit_strip, receive_strip, recover_strip, strip_auto_print_check
from gui.panels.workspace import WorkspaceWidget, WorkspaceWidget
from gui.panels.teachingConsole import TeachingConsole
from gui.panels.unitConv import UnitConversionWindow
from gui.panels.selectionInfo import SelectionInfoToolbarWidget
from gui.widgets.basicWidgets import AlarmClockButton
from gui.widgets.miscWidgets import RadioKeyEventFilter, QuickReference, WorldAirportNavigator
from gui.dialog.startSession import StartSoloDialog_AD, StartFlightGearMPdialog, StartStudentSessionDialog
from gui.dialog.settings import LocalSettingsDialog, GeneralSettingsDialog, SystemSettingsDialog, SoloSessionSettingsDialog
from gui.dialog.runways import RunwayUseDialog
from gui.dialog.miscDialogs import yesNo_question, AboutDialog, \
		PostLennySessionDialog, DiscardedStripsDialog, EnvironmentInfoDialog


# ---------- Constants ----------

subsecond_tick_interval = 333 # ms
subminute_tick_interval = 20 * 1000 # ms
status_bar_message_timeout = 5000 # ms
session_start_sound_lock_duration = 3000 # ms

dock_layout_file = 'settings/dock_layout'

dock_flash_stylesheet = 'QDockWidget::title { background: yellow }'
dock_flash_time = 750 # ms

OSM_zoom_level = 7
OSM_base_URL_fmt = 'http://www.openstreetmap.org/#map=%d/%f/%f'

airport_gateway_URL = 'http://gateway.x-plane.com/airports/page'
video_tutorial_URL = 'http://www.youtube.com/playlist?list=PL1EQKKHhDVJvvWpcX_BqeOIsmeW2A_8Yb'
FAQ_URL = 'http://wiki.flightgear.org/ATC-pie_FAQ'

# -------------------------------



def setDockAndActionIcon(icon_file, action, dock):
	icon = QIcon(icon_file)
	action.setIcon(icon)
	dock.setWindowIcon(icon)

def mk_OSM_URL(coords):
	return OSM_base_URL_fmt % (OSM_zoom_level, coords.lat, coords.lon)


class MainWindow(QMainWindow, Ui_mainWindow):
	def __init__(self, launcher, parent=None):
		QMainWindow.__init__(self, parent)
		self.setupUi(self)
		self.central_workspace = WorkspaceWidget(self)
		self.setCentralWidget(self.central_workspace)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.setAttribute(Qt.WA_DeleteOnClose)
		self.launcher = launcher
		settings.controlled_tower_viewer = FlightGearTowerViewer(self)
		settings.session_manager = SessionManager(self)
		self.setWindowTitle('%s - %s (%s)' % (self.windowTitle(), env.locationName(), settings.location_code))
		self.session_start_sound_lock_timer = QTimer(self)
		self.session_start_sound_lock_timer.setSingleShot(True)
		self.session_start_sound_lock_timer.timeout.connect(self.unlockSounds)
		
		## Restore saved dock layout
		try:
			with open(dock_layout_file, 'rb') as f: # Restore saved dock arrangement
				self.restoreState(f.read())
		except FileNotFoundError: # Fallback on default dock arrangement
			# left docks, top zone
			self.tabifyDockWidget(self.selection_info_dock, self.weather_dock)
			self.tabifyDockWidget(self.selection_info_dock, self.towerView_dock)
			self.tabifyDockWidget(self.selection_info_dock, self.navigator_dock)
			self.selection_info_dock.hide()
			# left docks, bottom zone
			self.tabifyDockWidget(self.instructions_dock, self.notepads_dock)
			self.tabifyDockWidget(self.instructions_dock, self.radio_dock)
			self.tabifyDockWidget(self.instructions_dock, self.FPLlist_dock)
			self.tabifyDockWidget(self.instructions_dock, self.CPDLC_dock)
			self.instructions_dock.hide()
			self.notepads_dock.hide()
			self.radio_dock.hide()
			self.CPDLC_dock.hide()
			# right docks
			self.rwyBoxes_dock.hide() # hiding this because bad position (user will drag 1st thing after raise)
			# bottom docks
			self.atcTextChat_dock.hide()
		
		## Permanent tool/status bar widgets
		self.selectionInfo_toolbar.addWidget(SelectionInfoToolbarWidget(self))
		self.METAR_statusBarLabel = QLabel()
		self.PTT_statusBarLabel = QLabel()
		self.RDF_statusBarLabel = QLabel()
		self.RDF_statusBarLabel.setToolTip('Current signal / last QDM')
		self.wind_statusBarLabel = QLabel()
		self.QNH_statusBarLabel = QLabel()
		self.QNH_statusBarLabel.setToolTip('hPa / inHg')
		self.clock_statusBarLabel = QLabel()
		self.alarmClock_statusBarButtons = [AlarmClockButton('1', self), AlarmClockButton('2', self)]
		self.statusbar.addWidget(self.METAR_statusBarLabel)
		self.statusbar.addPermanentWidget(self.PTT_statusBarLabel)
		self.statusbar.addPermanentWidget(self.RDF_statusBarLabel)
		self.statusbar.addPermanentWidget(self.wind_statusBarLabel)
		self.statusbar.addPermanentWidget(self.QNH_statusBarLabel)
		for b in self.alarmClock_statusBarButtons:
			self.statusbar.addPermanentWidget(b)
			b.alarm.connect(self.notification_pane.notifyAlarmClockTimedOut)
		self.statusbar.addPermanentWidget(self.clock_statusBarLabel)
		
		# Populate menus (toolbar visibility and airport viewpoints)
		toolbar_menu = QMenu()
		self.general_viewToolbar_action = self.general_toolbar.toggleViewAction()
		self.stripActions_viewToolbar_action = self.stripActions_toolbar.toggleViewAction()
		self.docks_viewToolbar_action = self.docks_toolbar.toggleViewAction()
		self.selectionInfo_viewToolbar_action = self.selectionInfo_toolbar.toggleViewAction()
		self.radarAssistance_viewToolbar_action = self.radarAssistance_toolbar.toggleViewAction()
		self.workspace_viewToolbar_action = self.workspace_toolbar.toggleViewAction()
		toolbar_menu.addAction(self.general_viewToolbar_action)
		toolbar_menu.addAction(self.stripActions_viewToolbar_action)
		toolbar_menu.addAction(self.docks_viewToolbar_action)
		toolbar_menu.addAction(self.selectionInfo_viewToolbar_action)
		toolbar_menu.addAction(self.radarAssistance_viewToolbar_action)
		toolbar_menu.addAction(self.workspace_viewToolbar_action)
		self.toolbars_view_menuAction.setMenu(toolbar_menu)
		
		if env.airport_data == None or len(env.airport_data.viewpoints) == 0:
			self.viewpointSelection_view_menuAction.setEnabled(False)
		else:
			viewPointSelection_menu = QMenu()
			viewPointSelection_actionGroup = QActionGroup(self)
			for vp_i, (vp_pos, vp_h, vp_name) in enumerate(env.airport_data.viewpoints):
				action = QAction('%s - %d ft ASFC' % (vp_name, vp_h + .5), self)
				action.setCheckable(True)
				action.triggered.connect(lambda ignore_checked, i=vp_i: self.selectIndicateViewpoint(i))
				viewPointSelection_actionGroup.addAction(action)
			actions = viewPointSelection_actionGroup.actions()
			viewPointSelection_menu.addActions(actions)
			self.viewpointSelection_view_menuAction.setMenu(viewPointSelection_menu)
			try:
				actions[settings.selected_viewpoint].setChecked(True)
			except IndexError:
				actions[0].setChecked(True)
		
		## Memory-persistent windows and dialogs
		self.solo_connect_dialog_AD = StartSoloDialog_AD(self)
		self.MP_connect_dialog = StartFlightGearMPdialog(self)
		self.start_student_session_dialog = StartStudentSessionDialog(self)
		self.recall_cheat_dialog = DiscardedStripsDialog(self, ShelfFilterModel(self, env.discarded_strips, False), 'Sent and deleted strips')
		self.shelf_dialog = DiscardedStripsDialog(self, ShelfFilterModel(self, env.discarded_strips, True), 'Strip shelf')
		self.environment_info_dialog = EnvironmentInfoDialog(self)
		self.about_dialog = AboutDialog(self)
		self.teaching_console = TeachingConsole(parent=self)
		self.unit_converter = UnitConversionWindow(parent=self)
		self.world_airport_navigator = WorldAirportNavigator(parent=self)
		self.quick_reference = QuickReference(parent=self)
		for w in self.teaching_console, self.unit_converter, self.world_airport_navigator, self.quick_reference:
			w.setWindowFlags(Qt.Window)
			w.installEventFilter(RadioKeyEventFilter(w))
		
		# Make a few actions always visible
		self.addAction(self.newStrip_action)
		self.addAction(self.newLinkedStrip_action)
		self.addAction(self.newFPL_action)
		self.addAction(self.newLinkedFPL_action)
		self.addAction(self.startTimer1_action)
		self.addAction(self.forceStartTimer1_action)
		self.addAction(self.startTimer2_action)
		self.addAction(self.forceStartTimer2_action)
		self.addAction(self.notificationSounds_options_action)
		self.addAction(self.quickReference_help_action)
		self.addAction(self.saveDockLayout_view_action)
		self.addAction(self.recallWindowState_view_action)
		
		# Populate icons
		self.newStrip_action.setIcon(QIcon(IconFile.action_newStrip))
		self.newLinkedStrip_action.setIcon(QIcon(IconFile.action_newLinkedStrip))
		self.newFPL_action.setIcon(QIcon(IconFile.action_newFPL))
		self.newLinkedFPL_action.setIcon(QIcon(IconFile.action_newLinkedFPL))
		self.teachingConsole_view_action.setIcon(QIcon(IconFile.panel_teaching))
		self.unitConversionTool_view_action.setIcon(QIcon(IconFile.panel_unitConv))
		self.worldAirportNavigator_view_action.setIcon(QIcon(IconFile.panel_airportList))
		self.environmentInfo_view_action.setIcon(QIcon(IconFile.panel_envInfo))
		self.generalSettings_options_action.setIcon(QIcon(IconFile.action_generalSettings))
		self.soloSessionSettings_system_action.setIcon(QIcon(IconFile.action_sessionSettings))
		self.runwaysInUse_options_action.setIcon(QIcon(IconFile.action_runwayUse))
		self.newLooseStripBay_view_action.setIcon(QIcon(IconFile.action_newLooseStripBay))
		self.newRadarScreen_view_action.setIcon(QIcon(IconFile.action_newRadarScreen))
		self.newStripRackPanel_view_action.setIcon(QIcon(IconFile.action_newRackPanel))
		self.popOutCurrentWindow_view_action.setIcon(QIcon(IconFile.action_popOutWindow))
		self.reclaimPoppedOutWindows_view_action.setIcon(QIcon(IconFile.action_reclaimWindows))
		self.primaryRadar_options_action.setIcon(QIcon(IconFile.option_primaryRadar))
		self.approachSpacingHints_options_action.setIcon(QIcon(IconFile.option_approachSpacingHints))
		self.runwayOccupationWarnings_options_action.setIcon(QIcon(IconFile.option_runwayOccupationMonitor))
		self.routeConflictWarnings_options_action.setIcon(QIcon(IconFile.option_routeConflictWarnings))
		self.trafficIdentification_options_action.setIcon(QIcon(IconFile.option_identificationAssistant))
		
		setDockAndActionIcon(IconFile.panel_ATCs, self.handovers_dockView_action, self.handover_dock)
		setDockAndActionIcon(IconFile.panel_atcChat, self.atcTextChat_dockView_action, self.atcTextChat_dock)
		setDockAndActionIcon(IconFile.panel_CPDLC, self.cpdlc_dockView_action, self.CPDLC_dock)
		setDockAndActionIcon(IconFile.panel_FPLs, self.FPLs_dockView_action, self.FPLlist_dock)
		setDockAndActionIcon(IconFile.panel_instructions, self.instructions_dockView_action, self.instructions_dock)
		setDockAndActionIcon(IconFile.panel_navigator, self.navpoints_dockView_action, self.navigator_dock)
		setDockAndActionIcon(IconFile.panel_notepads, self.notepads_dockView_action, self.notepads_dock)
		setDockAndActionIcon(IconFile.panel_notifications, self.notificationArea_dockView_action, self.notification_dock)
		setDockAndActionIcon(IconFile.panel_radios, self.fgcom_dockView_action, self.radio_dock)
		setDockAndActionIcon(IconFile.panel_runwayBox, self.runwayBoxes_dockView_action, self.rwyBoxes_dock)
		setDockAndActionIcon(IconFile.panel_selInfo, self.radarContactDetails_dockView_action, self.selection_info_dock)
		setDockAndActionIcon(IconFile.panel_racks, self.strips_dockView_action, self.strip_dock)
		setDockAndActionIcon(IconFile.panel_txtChat, self.radioTextChat_dockView_action, self.radioTextChat_dock)
		setDockAndActionIcon(IconFile.panel_twrView, self.towerView_dockView_action, self.towerView_dock)
		setDockAndActionIcon(IconFile.panel_weather, self.weather_dockView_action, self.weather_dock)
		
		# action TICKED STATES (set here before connections)
		self.windowedWorkspace_view_action.setChecked(settings.saved_workspace_windowed_view)
		self.verticalRwyBoxLayout_view_action.setChecked(settings.vertical_runway_box_layout)
		self.notificationSounds_options_action.setChecked(settings.notification_sounds_enabled)
		self.primaryRadar_options_action.setChecked(settings.primary_radar_active)
		self.routeConflictWarnings_options_action.setChecked(settings.route_conflict_warnings)
		self.trafficIdentification_options_action.setChecked(settings.traffic_identification_assistant)
		self.runwayOccupationWarnings_options_action.setChecked(settings.monitor_runway_occupation)
		self.approachSpacingHints_options_action.setChecked(settings.APP_spacing_hints)
		
		# action CONNECTIONS
		# non-menu actions
		self.newStrip_action.triggered.connect(lambda: new_strip_dialog(self, default_rack_name, linkToSelection=False))
		self.newLinkedStrip_action.triggered.connect(lambda: new_strip_dialog(self, default_rack_name, linkToSelection=True))
		self.newFPL_action.triggered.connect(lambda: self.FPLlist_pane.createLocalFPL(link=None))
		self.newLinkedFPL_action.triggered.connect(lambda: self.FPLlist_pane.createLocalFPL(link=selection.strip))
		self.startTimer1_action.triggered.connect(lambda: self.startTimer(0, False))
		self.forceStartTimer1_action.triggered.connect(lambda: self.startTimer(0, True))
		self.startTimer2_action.triggered.connect(lambda: self.startTimer(1, False))
		self.forceStartTimer2_action.triggered.connect(lambda: self.startTimer(1, True))
		# system menu
		self.soloSession_system_action.triggered.connect(lambda: self.startStopSession(self.start_solo))
		self.connectFlightGearMP_system_action.triggered.connect(lambda: self.startStopSession(self.start_FlightGearMP))
		self.teacherSession_system_action.triggered.connect(lambda: self.startStopSession(self.start_teaching))
		self.studentSession_system_action.triggered.connect(lambda: self.startStopSession(self.start_learning))
		self.reloadAdditionalViewers_system_action.triggered.connect(self.reloadAdditionalViewers)
		self.reloadBgImages_system_action.triggered.connect(self.reloadBackgroundImages)
		self.reloadColourConfig_system_action.triggered.connect(self.reloadColourConfig)
		self.reloadRoutePresets_system_action.triggered.connect(self.reloadRoutePresets)
		self.reloadEntryExitPoints_system_action.triggered.connect(self.reloadEntryExitPoints)
		self.announceFgSession_system_action.triggered.connect(self.announceFgSession)
		self.fgcomEchoTest_system_action.triggered.connect(self.radio_pane.performEchoTest)
		self.extractSectorFile_system_action.triggered.connect(self.extractSectorFile)
		self.repositionBgImages_system_action.triggered.connect(self.repositionRadarBgImages)
		self.measuringLogsCoordinates_system_action.toggled.connect(self.switchMeasuringCoordsLog)
		self.airportGateway_system_action.triggered.connect(lambda: self.goToURL(airport_gateway_URL))
		self.openStreetMap_system_action.triggered.connect(lambda: self.goToURL(mk_OSM_URL(env.radarPos())))
		self.soloSessionSettings_system_action.triggered.connect(self.openSoloSessionSettings)
		self.locationSettings_system_action.triggered.connect(self.openLocalSettings)
		self.systemSettings_system_action.triggered.connect(self.openSystemSettings)
		self.changeLocation_system_action.triggered.connect(self.changeLocation)
		self.quit_system_action.triggered.connect(self.close)
		# view menu
		self.saveDockLayout_view_action.triggered.connect(self.saveDockLayout)
		self.recallWindowState_view_action.triggered.connect(self.recallWindowState)
		self.handovers_dockView_action.triggered.connect(lambda: self.raiseDock(self.handover_dock))
		self.atcTextChat_dockView_action.triggered.connect(lambda: self.raiseDock(self.atcTextChat_dock))
		self.cpdlc_dockView_action.triggered.connect(lambda: self.raiseDock(self.CPDLC_dock))
		self.FPLs_dockView_action.triggered.connect(lambda: self.raiseDock(self.FPLlist_dock))
		self.instructions_dockView_action.triggered.connect(lambda: self.raiseDock(self.instructions_dock))
		self.navpoints_dockView_action.triggered.connect(lambda: self.raiseDock(self.navigator_dock))
		self.notepads_dockView_action.triggered.connect(lambda: self.raiseDock(self.notepads_dock))
		self.notificationArea_dockView_action.triggered.connect(lambda: self.raiseDock(self.notification_dock))
		self.fgcom_dockView_action.triggered.connect(lambda: self.raiseDock(self.radio_dock))
		self.runwayBoxes_dockView_action.triggered.connect(lambda: self.raiseDock(self.rwyBoxes_dock))
		self.radarContactDetails_dockView_action.triggered.connect(lambda: self.raiseDock(self.selection_info_dock))
		self.strips_dockView_action.triggered.connect(lambda: self.raiseDock(self.strip_dock))
		self.radioTextChat_dockView_action.triggered.connect(lambda: self.raiseDock(self.radioTextChat_dock))
		self.towerView_dockView_action.triggered.connect(lambda: self.raiseDock(self.towerView_dock))
		self.weather_dockView_action.triggered.connect(lambda: self.raiseDock(self.weather_dock))
		self.windowedWorkspace_view_action.toggled.connect(self.central_workspace.switchWindowedView)
		self.popOutCurrentWindow_view_action.triggered.connect(self.central_workspace.popOutCurrentWindow)
		self.reclaimPoppedOutWindows_view_action.triggered.connect(self.central_workspace.reclaimPoppedOutWidgets)
		self.newLooseStripBay_view_action.triggered.connect(lambda: self.central_workspace.addWorkspaceWidget(WorkspaceWidget.LOOSE_BAY))
		self.newRadarScreen_view_action.triggered.connect(lambda: self.central_workspace.addWorkspaceWidget(WorkspaceWidget.RADAR_SCREEN))
		self.newStripRackPanel_view_action.triggered.connect(lambda: self.central_workspace.addWorkspaceWidget(WorkspaceWidget.STRIP_PANEL))
		self.verticalRwyBoxLayout_view_action.toggled.connect(self.switchVerticalRwyBoxLayout)
		self.towerView_view_action.triggered.connect(self.toggleTowerWindow)
		self.addViewer_view_action.triggered.connect(self.addView)
		self.listViewers_view_action.triggered.connect(self.listAdditionalViews)
		self.activateAdditionalViewers_view_action.toggled.connect(self.activateAdditionalViews)
		self.removeViewer_view_action.triggered.connect(self.removeView)
		self.teachingConsole_view_action.triggered.connect(self.teaching_console.show)
		self.unitConversionTool_view_action.triggered.connect(self.unit_converter.show)
		self.worldAirportNavigator_view_action.triggered.connect(self.world_airport_navigator.show)
		self.environmentInfo_view_action.triggered.connect(self.environment_info_dialog.exec)
		# options menu
		self.runwaysInUse_options_action.triggered.connect(self.configureRunwayUse)
		self.notificationSounds_options_action.toggled.connect(self.switchNotificationSounds)
		self.primaryRadar_options_action.toggled.connect(self.switchPrimaryRadar)
		self.routeConflictWarnings_options_action.toggled.connect(self.switchConflictWarnings)
		self.trafficIdentification_options_action.toggled.connect(self.switchTrafficIdentification)
		self.runwayOccupationWarnings_options_action.toggled.connect(self.switchRwyOccupationIndications)
		self.approachSpacingHints_options_action.toggled.connect(self.switchApproachSpacingHints)
		self.generalSettings_options_action.triggered.connect(self.openGeneralSettings)
		# cheat menu
		self.pauseSimulation_cheat_action.toggled.connect(self.pauseSession)
		self.spawnAircraft_cheat_action.triggered.connect(self.spawnAircraft)
		self.killSelectedAircraft_cheat_action.triggered.connect(self.killSelectedAircraft)
		self.popUpMsgOnRejectedInstr_cheat_action.toggled.connect(self.setRejectedInstrPopUp)
		self.showRecognisedVoiceStrings_cheat_action.toggled.connect(self.setShowRecognisedVoiceStrings)
		self.ensureClearWeather_cheat_action.toggled.connect(self.ensureClearWeather)
		self.ensureDayLight_cheat_action.triggered.connect(self.towerView_pane.ensureDayLight)
		self.changeTowerHeight_cheat_action.triggered.connect(self.changeTowerHeight)
		self.recallDiscardedStrip_cheat_action.triggered.connect(self.recall_cheat_dialog.exec)
		self.radarCheatMode_cheat_action.toggled.connect(self.setRadarCheatMode)
		# help menu
		self.quickReference_help_action.triggered.connect(self.quick_reference.show)
		self.videoTutorial_help_action.triggered.connect(lambda: self.goToURL(video_tutorial_URL))
		self.FAQ_help_action.triggered.connect(lambda: self.goToURL(FAQ_URL))
		self.about_help_action.triggered.connect(self.about_dialog.exec)
		
		## More signal connections
		signals.openShelfRequest.connect(self.shelf_dialog.exec)
		signals.privateAtcChatRequest.connect(lambda: self.raiseDock(self.atcTextChat_dock))
		signals.stripRecall.connect(recover_strip)
		env.radar.blip.connect(env.strips.refreshViews)
		env.radar.lostContact.connect(self.aircraftHasDisappeared)
		signals.aircraftKilled.connect(self.aircraftHasDisappeared)
		env.strips.rwyBoxFreed.connect(lambda box, strip: env.airport_data.physicalRunway_restartWtcTimer(box, strip.lookup(FPL.WTC)))
		env.rdf.signalChanged.connect(self.updateRDF)
		signals.statusBarMsg.connect(lambda msg: self.statusbar.showMessage(msg, status_bar_message_timeout))
		signals.newWeather.connect(self.updateWeatherIfPrimary)
		signals.kbdPTT.connect(self.updatePTT)
		signals.sessionStarted.connect(self.sessionHasStarted)
		signals.sessionEnded.connect(self.sessionHasEnded)
		signals.towerViewProcessToggled.connect(self.towerView_view_action.setChecked)
		signals.towerViewProcessToggled.connect(self.towerView_cheat_menu.setEnabled)
		signals.stripInfoChanged.connect(env.strips.refreshViews)
		signals.fastClockTick.connect(self.updateClock)
		signals.fastClockTick.connect(env.cpdlc.updateAckStatuses)
		signals.slowClockTick.connect(strip_auto_print_check)
		signals.stripEditRequest.connect(lambda strip: edit_strip(self, strip))
		signals.selectionChanged.connect(self.updateStripFplActions)
		signals.receiveStrip.connect(receive_strip)
		signals.handoverFailure.connect(self.recoverFailedHandover)
		signals.sessionPaused.connect(env.radar.stopSweeping)
		signals.sessionResumed.connect(env.radar.startSweeping)
		signals.aircraftKilled.connect(env.radar.silentlyForgetContact)
		signals.rackVisibilityLost.connect(self.collectClosedRacks)
		signals.localSettingsChanged.connect(env.rdf.clearAllSignals)
		signals.localSettingsChanged.connect(self.updateRDF)
		
		## MISC GUI setup
		self.strip_pane.setViewRacks([default_rack_name]) # will be moved out if a rack panel's saved "visible_racks" claims it [*1]
		self.strip_pane.restoreState(settings.saved_strip_dock_state) # [*1]
		self.central_workspace.restoreWorkspaceWindows(settings.saved_workspace_windows)
		self.central_workspace.switchWindowedView(settings.saved_workspace_windowed_view) # keep this after restoring windows!
		
		self.subsecond_ticker = Ticker(signals.fastClockTick.emit, parent=self)
		self.subminute_ticker = Ticker(signals.slowClockTick.emit, parent=self)
		self.subsecond_ticker.start_stopOnZero(subsecond_tick_interval)
		self.subminute_ticker.start_stopOnZero(subminute_tick_interval)
		self.towerView_cheat_menu.setEnabled(False)
		self.solo_cheat_menu.setEnabled(False)
		self.updateClock()
		self.updateWeatherIfPrimary(settings.primary_METAR_station, None)
		self.updateStripFplActions()
		self.last_RDF_qdm = None
		self.updateRDF()
		self.updatePTT(0, False)
		# Disable some base airport stuff if doing CTR
		if env.airport_data == None:
			self.towerView_view_action.setEnabled(False)
			self.runwaysInUse_options_action.setEnabled(False)
			self.runwayOccupationWarnings_options_action.setEnabled(False)
		# Finish
		self.atcTextChat_pane.switchAtcChatFilter(None) # Show GUI on general chat room at start
		if speech_recognition_available:
			prepare_SR_language_files()
	
	def raiseDock(self, dock):
		dock.show()
		dock.raise_()
		dock.widget().setFocus()
		dock.setStyleSheet(dock_flash_stylesheet)
		QTimer.singleShot(dock_flash_time, lambda: dock.setStyleSheet(None))
	
	def startTimer(self, i, force_start):
		if force_start or not self.alarmClock_statusBarButtons[i].timerIsRunning():
			self.alarmClock_statusBarButtons[i].setTimer()
	
	def goToURL(self, url):
		if not QDesktopServices.openUrl(QUrl(url)):
			QMessageBox.critical(self, 'Error opening web browser', \
				'Could not invoke desktop web browser.\nGo to: %s' % url)

	def recoverFailedHandover(self, strip, msg):
		recover_strip(strip)
		QMessageBox.critical(self, 'Handover failed', '%s\nStrip has been recovered.' % msg)
	
	
	
	
	
	
	# ---------------------     GUI auto-update functions     ---------------------- #
	
	def updateClock(self):
		self.clock_statusBarLabel.setText('UTC ' + timestr(seconds=True))
	
	def unlockSounds(self):
		settings.session_start_sound_lock = False
	
	def updateWeatherIfPrimary(self, station, weather): # NOTE weather may be None here
		if station == settings.primary_METAR_station:
			# Update status bar info
			self.METAR_statusBarLabel.setText(None if weather == None else weather.METAR())
			self.wind_statusBarLabel.setText('Wind ' + ('---' if weather == None else weather.readWind()))
			qnh = None if weather == None else weather.QNH() # NOTE qnh may still be None
			self.QNH_statusBarLabel.setText('QNH ' + ('%d / %.2f' % (qnh, hPa2inHg * qnh) if qnh != None else '---'))
			# Update tower view
			if weather != None and not settings.TWR_view_clear_weather_cheat:
				settings.controlled_tower_viewer.setWeather(weather)
	
	def updatePTT(self, button, pressed):
		if settings.session_manager.isRunning():
			settings.transmitting_radio = pressed
			if settings.session_manager.session_type == SessionType.SOLO:
				if settings.solo_voice_instructions:
					self.PTT_statusBarLabel.setText('PTT' if pressed else 'VOICE')
				else:
					self.PTT_statusBarLabel.setText('MOUSE')
			elif pressed:
				self.PTT_statusBarLabel.setText('PTT')
			else:
				self.PTT_statusBarLabel.setText(' - - - ')
		else:
			settings.transmitting_radio = False
			self.PTT_statusBarLabel.setText('Off')
	
	def updateRDF(self):
		self.RDF_statusBarLabel.setVisible(settings.radio_direction_finding)
		if settings.radio_direction_finding:
			hdg = env.rdf.currentSignalRadial()
			if hdg == None:
				s1 = ' - - - '
			else:
				self.last_RDF_qdm = hdg.opposite()
				s1 = hdg.read()
			s2 = ' - - - ' if self.last_RDF_qdm == None else self.last_RDF_qdm.read()
			self.RDF_statusBarLabel.setText('RDF %s / %s' % (s1, s2))
	
	def updateSessionStartStopActions(self):
		running = settings.session_manager.isRunning()
		for gt, ma in {
					SessionType.SOLO: self.soloSession_system_action,
					SessionType.FLIGHTGEAR_MP: self.connectFlightGearMP_system_action,
					SessionType.STUDENT: self.studentSession_system_action,
					SessionType.TEACHER: self.teacherSession_system_action
				}.items():
			if gt == settings.session_manager.session_type:
				ma.setEnabled(True)
				ma.setChecked(running)
			else:
				ma.setEnabled(not running)
				ma.setChecked(False)
	
	def updateStripFplActions(self):
		self.newLinkedStrip_action.setEnabled(selection.strip == None and not selection.acft == selection.fpl == None)
		self.newLinkedFPL_action.setEnabled(selection.strip != None and selection.strip.linkedFPL() == None)
	
	def sessionHasStarted(self):
		self.session_start_sound_lock_timer.start(session_start_sound_lock_duration)
		self.updateSessionStartStopActions()
		self.solo_cheat_menu.setEnabled(settings.session_manager.session_type == SessionType.SOLO)
		self.updatePTT(0, False)
		env.radar.startSweeping()
		
	def sessionHasEnded(self):
		env.radar.stopSweeping()
		env.radar.resetContacts()
		env.strips.removeAllStrips()
		env.FPLs.clearFPLs()
		env.rdf.clearAllSignals()
		env.cpdlc.clearHistory()
		self.updateSessionStartStopActions()
		self.pauseSimulation_cheat_action.setChecked(False)
		self.solo_cheat_menu.setEnabled(False)
		self.updatePTT(0, False)
		self.last_RDF_qdm = None
		self.updateRDF()
		print('Session ended.')
	
	def aircraftHasDisappeared(self, acft):
		strip = env.linkedStrip(acft)
		if strip != None:
			strip.linkAircraft(None)
		if selection.acft is acft:
			if strip == None: # was not linked
				selection.deselect()
			else:
				selection.selectStrip(strip)
	
	def collectClosedRacks(self, racks):
		self.strip_pane.setViewRacks(self.strip_pane.getViewRacks() + racks)
	
	
	
	
	
	
	# ---------------------     Session start functions     ---------------------- #
	
	def start_solo(self):
		if env.airport_data == None: # start CTR solo simulation
			n, ok = QInputDialog.getInt(self, 'Solo CTR session', 'Initial traffic count:', value=2, min=0, max=99)
			if ok:
				settings.session_manager = SoloSessionManager_CTR(self)
				settings.session_manager.start(n)
		else: # start AD solo simulation
			self.solo_connect_dialog_AD.exec()
			if self.solo_connect_dialog_AD.result() > 0: # not rejected
				settings.session_manager = SoloSessionManager_AD(self)
				settings.session_manager.start(self.solo_connect_dialog_AD.chosenInitialTrafficCount())
	
	def start_FlightGearMP(self):
		self.MP_connect_dialog.exec()
		if self.MP_connect_dialog.result() > 0: # not rejected
			settings.session_manager = FlightGearMultiPlayerSessionManager(self, self.MP_connect_dialog.chosenCallsign())
			settings.session_manager.start()
	
	def start_teaching(self):
		port, ok = QInputDialog.getInt(self, 'Start a teaching session', 'Service port:', value=settings.teaching_service_port, max=99999)
		if ok:
			settings.teaching_service_port = port
			settings.session_manager = TeacherSessionManager(self)
			settings.session_manager.start()
	
	def start_learning(self):
		self.start_student_session_dialog.exec()
		if self.start_student_session_dialog.result() > 0: # not rejected
			settings.session_manager = StudentSessionManager(self)
			settings.session_manager.start()
	
	
	
	
	
	
	# ---------------------     GUI menu actions     ---------------------- #
	
	## SYSTEM MENU ##
	
	def startStopSession(self, start_func):
		if settings.session_manager.isRunning(): # Stop session
			selection.deselect()
			env.cpdlc.endAllDataLinks()
			settings.session_manager.stop()
		else: # Start session
			settings.session_start_sound_lock = True
			start_func()
		self.updateSessionStartStopActions()
		if not settings.session_manager.isRunning():
			settings.session_start_sound_lock = False
	
	def reloadAdditionalViewers(self):
		print('Reload: additional viewers')
		settings.loadAdditionalViews()
		QMessageBox.information(self, 'Done reloading', 'Additional viewers reloaded. Check for console error messages.')
	
	def reloadBackgroundImages(self):
		print('Reload: background images')
		settings.radar_background_images, settings.loose_strip_bay_backgrounds = read_bg_img(settings.location_code, env.navpoints)
		signals.backgroundImagesReloaded.emit()
		QMessageBox.information(self, 'Done reloading', 'Background images reloaded. Check for console error messages.')
	
	def reloadColourConfig(self):
		print('Reload: colour configuration')
		settings.loadColourSettings()
		signals.colourConfigReloaded.emit()
		QMessageBox.information(self, 'Done reloading', 'Colour configuration reloaded. Check for console error messages.')
	
	def reloadRoutePresets(self):
		print('Reload: route presets')
		settings.route_presets = read_route_presets()
		QMessageBox.information(self, 'Done reloading', 'Route presets reloaded. Check for console error messages.')
	
	def reloadEntryExitPoints(self):
		print('Reload: entry/exit points')
		world_routing_db.clearEntryExitPoints()
		import_entry_exit_data()
		QMessageBox.information(self, 'Done reloading', 'Entry/exit points reloaded. Check for console error messages.')
	
	def announceFgSession(self):
		if settings.lenny64_account_email == '':
			QMessageBox.critical(self, 'Lenny64 account details missing', \
				'This feature requires a Lenny64 dashboard. Please provide one in the FlightGear system set-up tab.')
		else:
			PostLennySessionDialog(self).exec()
	
	def switchMeasuringCoordsLog(self, toggle):
		settings.measuring_tool_logs_coordinates = toggle
	
	def extractSectorFile(self):
		txt, ignore = QFileDialog.getOpenFileName(self, caption='Select sector file to extract from')
		if txt != '':
			extract_sector(txt, env.radarPos(), settings.map_range)
			QMessageBox.information(self, 'Done extracting', \
				'Background drawings extracted.\nSee console for summary and files created in the output directory.')
	
	def repositionRadarBgImages(self):
		radar_panel = self.central_workspace.getCurrentRadarPanel()
		if radar_panel == None:
			QMessageBox.critical(self, 'Image positioning error', 'This requires an active radar panel in the central workspace.')
		else:
			radar_panel.positionVisibleBgImages()
	
	def openSoloSessionSettings(self):
		SoloSessionSettingsDialog(self).exec()
		self.updatePTT(0, False) # display "MOUSE/VOICE" as appropriate
	
	def openLocalSettings(self):
		dialog = LocalSettingsDialog(self)
		dialog.exec()
		if dialog.result() > 0 and settings.session_manager.isRunning():
			env.radar.startSweeping()
	
	def openSystemSettings(self):
		SystemSettingsDialog(self).exec()
	
	def changeLocation(self):
		if yesNo_question(self, 'Change location', 'This will close the current session.', 'Are you sure?'):
			self.launcher.show()
			self.close()
	
	
	## VIEW MENU ##
	
	def saveDockLayout(self): # STYLE catch file write error
		with open(dock_layout_file, 'wb') as f:
			f.write(self.saveState())
		QMessageBox.information(self, 'Save dock layout', 'Current dock layout saved.')
	
	def recallWindowState(self):
		try:
			with open(dock_layout_file, 'rb') as f:
				self.restoreState(f.read())
		except FileNotFoundError:
			QMessageBox.critical(self, 'Recall dock layout', 'No saved layout to recall.')
	
	def switchVerticalRwyBoxLayout(self, toggle):
		settings.vertical_runway_box_layout = toggle
		self.rwyBox_pane.setVerticalLayout(settings.vertical_runway_box_layout)
	
	def toggleTowerWindow(self):
		if self.towerView_view_action.isChecked():
			if env.airport_data != None and len(env.airport_data.viewpoints) == 0:
				QMessageBox.warning(self, 'No viewpoint', \
						'Airport data does not specify a viewpoint. ATC-pie is positioning one near a runway.\n'\
						'Update your source file if one should be available.')
			settings.controlled_tower_viewer.start()
		else:
			settings.controlled_tower_viewer.stop()
	
	def selectIndicateViewpoint(self, vp_index):
		if vp_index != settings.selected_viewpoint:
			settings.selected_viewpoint = vp_index
			settings.tower_height_cheat_offset = 0
			if settings.controlled_tower_viewer.running:
				self.towerView_pane.updateTowerPosition()
		signals.indicatePoint.emit(env.viewpoint()[0])
	
	def activateAdditionalViews(self, toggle):
		settings.additional_views_active = toggle
	
	def listAdditionalViews(self):
		if settings.additional_views == []:
			txt = 'No additional viewers registered.'
		else:
			lst = [' - %s on port %d' % host_port for host_port in settings.additional_views]
			txt = 'Additional viewers:\n%s' % '\n'.join(lst)
		QMessageBox.information(self, 'Additional viewers', txt)
	
	def addView(self):
		text, ok = QInputDialog.getText(self, 'Add an external viewer', 'Enter "host:port" to send traffic to:')
		if ok:
			split = text.rsplit(':', maxsplit=1)
			if len(split) == 2 and split[1].isdecimal():
				viewer_address = split[0], int(split[1])
				settings.additional_views.append(viewer_address)
				QMessageBox.information(self, 'Add an external viewer', 'Viewer added: %s on port %d.' % viewer_address)
			else:
				QMessageBox.critical(self, 'Add an external viewer', 'Bad "host:port" format.')
	
	def removeView(self):
		if settings.additional_views == []:
			QMessageBox.critical(self, 'Remove viewer', 'No additional viewers registered.')
		else:
			items = ['%d: %s on port %d' % (i, settings.additional_views[i][0], settings.additional_views[i][1]) \
								for i in range(len(settings.additional_views))]
			item, ok = QInputDialog.getItem(self, 'Remove viewer', 'Select viewer to remove:', items, editable=False)
			if ok:
				del settings.additional_views[int(item.split(':', maxsplit=1)[0])]
	
	
	## OPTIONS MENU ##
	
	def configureRunwayUse(self):
		RunwayUseDialog(self).exec()
	
	def switchNotificationSounds(self, toggle):
		settings.notification_sounds_enabled = toggle
	
	def switchPrimaryRadar(self, toggle):
		settings.primary_radar_active = toggle
		env.radar.scan()
	
	def switchConflictWarnings(self, toggle):
		settings.route_conflict_warnings = toggle
	
	def switchTrafficIdentification(self, toggle):
		settings.traffic_identification_assistant = toggle
		if not toggle:
			for strip in env.strips.listStrips():
				strip.writeDetail(soft_link_detail, None)
			signals.stripInfoChanged.emit()
	
	def switchRwyOccupationIndications(self, toggle):
		settings.monitor_runway_occupation = toggle
	
	def switchApproachSpacingHints(self, toggle):
		settings.APP_spacing_hints = toggle
		signals.stripInfoChanged.emit()
	
	def openGeneralSettings(self):
		GeneralSettingsDialog(self).exec()
	
	
	## CHEAT MENU ##
	
	def pauseSession(self, toggle):
		if toggle:
			settings.session_manager.pauseSession()
		else:
			settings.session_manager.resumeSession()
	
	def spawnAircraft(self):
		n, ok = QInputDialog.getInt(self, 'Spawn new aircraft', 'Try to spawn:', value=1, min=1, max=99)
		if ok:
			for i in range(n): # WARNING: session should be running
				settings.session_manager.spawnNewControlledAircraft()
	
	def killSelectedAircraft(self):
		selected = selection.acft
		if selected == None:
			QMessageBox.critical(self, 'Cheat error', 'No aircraft selected.')
		else:
			selection.deselect()
			settings.session_manager.killAircraft(selected) # WARNING: killAircraft method must exist
			env.radar.scan()
	
	def setRejectedInstrPopUp(self, toggle):
		settings.solo_erroneous_instruction_warning = toggle
	
	def ensureClearWeather(self, toggle):
		settings.TWR_view_clear_weather_cheat = toggle
		if toggle:
			weather = mkWeather(settings.location_code) # clear weather with location code as station
			settings.controlled_tower_viewer.setWeather(weather)
		else:
			weather = env.primaryWeather()
			if weather != None:
				settings.controlled_tower_viewer.setWeather(weather)
	
	def setShowRecognisedVoiceStrings(self, toggle):
		settings.show_recognised_voice_strings = toggle
	
	def changeTowerHeight(self):
		hoff, ok = QInputDialog.getInt(self, 'Cheat tower height', \
			'Offset in feet:', value=settings.tower_height_cheat_offset, min=0, max=1500, step=10)
		if ok:
			settings.tower_height_cheat_offset = hoff
			self.towerView_pane.updateTowerPosition()
	
	def setRadarCheatMode(self, toggle):
		settings.radar_cheat = toggle
		env.radar.scan()
	
	
	
	
	
	
	# -----------------     Internal GUI events      ------------------ #
	
	def closeEvent(self, event):
		if settings.session_manager.isRunning():
			settings.session_manager.stop()
		if settings.controlled_tower_viewer.running:
			settings.controlled_tower_viewer.stop(wait=True)
		if speech_recognition_available:
			cleanup_SR_language_files()
		print('Closing main window.')
		settings.saved_strip_racks = env.strips.rackNames()
		settings.saved_strip_dock_state = self.strip_pane.stateSave()
		settings.saved_workspace_windowed_view = self.central_workspace.windowedView()
		settings.saved_workspace_windows = self.central_workspace.workspaceWindowsStateSave()
		signals.mainWindowClosing.emit()
		signals.disconnect()
		settings.saveGeneralAndSystemSettings()
		settings.saveLocalSettings(env.airport_data)
		settings.savePresetChatMessages()
		env.resetEnv()
		settings.resetSession()
		EarthCoords.clearRadarPos()
		QMainWindow.closeEvent(self, event)

