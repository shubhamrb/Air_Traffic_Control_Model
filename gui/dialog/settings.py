
from datetime import timedelta
from hashlib import md5

from PyQt5.QtCore import Qt, QStringListModel
from PyQt5.QtWidgets import QWidget, QTabWidget, QDialog, QMessageBox, QInputDialog, QFileDialog

from ui.localSettingsDialog import Ui_localSettingsDialog
from ui.generalSettingsDialog import Ui_generalSettingsDialog
from ui.systemSettingsDialog import Ui_systemSettingsDialog
from ui.soloSessionSettingsDialog import Ui_soloSessionSettingsDialog

from session.config import settings, XpdrAssignmentRange
from session.env import env

from data.util import all_diff, some
from data.acft import snapshot_history_size
from data.params import StdPressureAlt
from data.nav import Navpoint

from ext.fgfs import fgTwrCommonOptions
from ext.tts import speech_synthesis_available
from ext.sr import speech_recognition_available, get_pyaudio_devices_info

from gui.misc import signals
from gui.widgets.miscWidgets import RadioKeyEventFilter
from gui.dialog.runways import RunwayParametersWidget


# ---------- Constants ----------

# -------------------------------


def short_pyaudio_device_info(info_dict):
	return '%d / %d / %g' % (info_dict['maxInputChannels'], info_dict['maxOutputChannels'], info_dict['defaultSampleRate'])



class SemiCircRule:
	rules = OFF, E_W, N_S = range(3)




# =================================
#
#           S Y S T E M
#
# =================================

class SystemSettingsDialog(QDialog, Ui_systemSettingsDialog):
	#STATIC:
	last_tab_used = 0
	
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.towerView_page.setEnabled(env.airport_data != None and not settings.controlled_tower_viewer.running)
		self.fgcom_page.setEnabled(not settings.session_manager.isRunning())
		self.flightgearMP_page.setEnabled(not settings.session_manager.isRunning())
		self.solo_page.setEnabled(not settings.session_manager.isRunning())
		self.SR_groupBox.setEnabled(speech_recognition_available)
		if speech_recognition_available:
			self.audio_devices = get_pyaudio_devices_info()
			self.sphinxAcousticModel_edit.setClearButtonEnabled(True)
			self.audioDeviceIndex_edit.setMaximum(len(self.audio_devices) - 1)
			self.audioDeviceInfo_button.clicked.connect(self.showAudioDeviceInfo)
		self.lennyPassword_edit.setPlaceholderText('No password set' if settings.lenny64_password_md5 == '' else '(unchanged)')
		self.fillFromSettings()
		self.settings_tabs.setCurrentIndex(SystemSettingsDialog.last_tab_used)
		self.produceExtViewerCmd_button.clicked.connect(self.showExternalViewerFgOptions)
		self.lennyPassword_edit.textChanged.connect(self._pwdTextChanged)
		self.browseForSphinxAcousticModel_button.clicked.connect(self.browseForSphinxAcousticModel)
		self.buttonBox.accepted.connect(self.storeSettings)
	
	def _pwdTextChanged(self, s):
		self.passwordChange_info.setText('Password will be changed!' if s != '' and settings.lenny64_password_md5 != '' else '')
	
	def browseForSphinxAcousticModel(self):
		txt = QFileDialog.getExistingDirectory(self, caption='Choose Sphinx acoustic model directory')
		if txt != '':
			self.sphinxAcousticModel_edit.setText(txt)
	
	def showAudioDeviceInfo(self):
		txt = 'PyAudio detects %d devices.\n[index] name: input channels / output channels / default sample rate\n' % len(self.audio_devices)
		for index, info in enumerate(self.audio_devices):
			txt += '\n[%d] %s: %s' % (index, info.get('name', '???'), short_pyaudio_device_info(info))
		QMessageBox.information(self, 'PyAudio devices information', txt)
	
	def showExternalViewerFgOptions(self):
		required_options = fgTwrCommonOptions()
		required_options.append('--multiplay=out,100,this_host,%d' % settings.FGFS_views_send_port)
		required_options.append('--multiplay=in,100,,%d' % self.towerView_fgmsPort_edit.value())
		required_options.append('--telnet=,,100,,%d,' % self.towerView_telnetPort_edit.value())
		print('Options required for external FlightGear viewer with current dialog options: ' + ' '.join(required_options))
		msg = 'Options required with present configuration (also sent to console):\n'
		msg += '\n'.join('  ' + opt for opt in required_options)
		msg += '\n\nNB: Replace "this_host" with appropriate value.'
		QMessageBox.information(self, 'Required FlightGear options', msg)

	def fillFromSettings(self):
		## Tower view
		(self.towerView_external_radioButton if settings.external_tower_viewer_process else self.towerView_internal_radioButton).setChecked(True)
		self.towerView_fgmsPort_edit.setValue(settings.tower_viewer_UDP_port)
		self.towerView_telnetPort_edit.setValue(settings.tower_viewer_telnet_port)
		self.fgCommand_edit.setText(settings.FGFS_executable)
		self.fgRootDir_edit.setText(settings.FGFS_root_dir)
		self.fgAircraftDir_edit.setText(settings.FGFS_aircraft_dir)
		self.fgSceneryDir_edit.setText(settings.FGFS_scenery_dir)
		self.externalTowerViewerHost_edit.setText(settings.external_tower_viewer_host)
		## FGCom
		self.fgcomExe_edit.setText(settings.fgcom_executable_path)
		self.fgcomServer_edit.setText(settings.fgcom_server)
		self.fgcomReservedPort_edit.setValue(settings.reserved_fgcom_port)
		self.fgcomRadioBoxPorts_edit.setText(','.join(str(n) for n in settings.radio_fgcom_ports))
		## FlightGear MP
		self.fgmsServerHost_edit.setText(settings.FGMS_server_name)
		self.fgmsServerPort_edit.setValue(settings.FGMS_server_port)
		self.fgmsLegacyProtocol_tickBox.setChecked(settings.FGMS_legacy_protocol)
		self.nickname_edit.setText(settings.MP_social_name)
		self.ircServerHost_edit.setText(settings.MP_IRC_server_name)
		self.ircServerPort_edit.setValue(settings.MP_IRC_server_port)
		self.ircChannel_edit.setText(settings.MP_IRC_channel)
		self.orsxServer_edit.setText(settings.ORSX_server_name)
		self.orsxHandoverRange_edit.setValue(some(settings.ORSX_handover_range, 0))
		self.lennyAccountEmail_edit.setText(settings.lenny64_account_email)
		self.lennyPassword_edit.setText('') # unchanged if stays blank
		self.FPLupdateInterval_edit.setValue(int(settings.FPL_update_interval.total_seconds()) / 60)
		self.METARupdateInterval_edit.setValue(int(settings.METAR_update_interval.total_seconds()) / 60)
		## Solo and teacher session types
		self.soloAircraftTypes_edit.setPlainText('\n'.join(settings.solo_aircraft_types))
		self.restrictAirlineChoiceToLiveries_tickBox.setChecked(settings.solo_restrict_to_available_liveries)
		self.preferEntryExitAirports_tickBox.setChecked(settings.solo_prefer_entry_exit_ADs)
		self.sphinxAcousticModel_edit.setText(settings.sphinx_acoustic_model_dir)
		self.audioDeviceIndex_edit.setValue(settings.audio_input_device_index)

	def storeSettings(self):
		try:
			fgcom_reserved_port = self.fgcomReservedPort_edit.value()
			fgcom_radio_ports = [int(p) for p in self.fgcomRadioBoxPorts_edit.text().split(',')]
			if fgcom_reserved_port in fgcom_radio_ports or not all_diff(fgcom_radio_ports):
				raise ValueError
		except ValueError:
			QMessageBox.critical(self, 'Invalid entry', 'Error or duplicates in FGCom port configuration.')
			return
		
		SystemSettingsDialog.last_tab_used = self.settings_tabs.currentIndex()
		
		## Tower view
		settings.external_tower_viewer_process = self.towerView_external_radioButton.isChecked()
		settings.tower_viewer_UDP_port = self.towerView_fgmsPort_edit.value()
		settings.tower_viewer_telnet_port = self.towerView_telnetPort_edit.value()
		settings.FGFS_executable = self.fgCommand_edit.text()
		settings.FGFS_root_dir = self.fgRootDir_edit.text()
		settings.FGFS_aircraft_dir = self.fgAircraftDir_edit.text()
		settings.FGFS_scenery_dir = self.fgSceneryDir_edit.text()
		settings.external_tower_viewer_host = self.externalTowerViewerHost_edit.text()
		
		## FGCom
		settings.fgcom_executable_path = self.fgcomExe_edit.text()
		settings.fgcom_server = self.fgcomServer_edit.text()
		settings.reserved_fgcom_port = fgcom_reserved_port
		settings.radio_fgcom_ports = fgcom_radio_ports
		
		## FlightGear MP
		settings.FGMS_server_name = self.fgmsServerHost_edit.text()
		settings.FGMS_server_port = self.fgmsServerPort_edit.value()
		settings.FGMS_legacy_protocol = self.fgmsLegacyProtocol_tickBox.isChecked()
		settings.MP_social_name = self.nickname_edit.text()
		settings.MP_IRC_server_name = self.ircServerHost_edit.text()
		settings.MP_IRC_server_port = self.ircServerPort_edit.value()
		settings.MP_IRC_channel = self.ircChannel_edit.text()
		settings.ORSX_server_name = self.orsxServer_edit.text()
		settings.ORSX_handover_range = None if self.orsxHandoverRange_edit.value() == 0 else self.orsxHandoverRange_edit.value()
		settings.lenny64_account_email = self.lennyAccountEmail_edit.text()
		new_lenny64_pwd = self.lennyPassword_edit.text()
		if new_lenny64_pwd != '': # password change!
			digester = md5()
			digester.update(bytes(new_lenny64_pwd, 'utf8'))
			settings.lenny64_password_md5 = ''.join('%02x' % x for x in digester.digest())
		settings.METAR_update_interval = timedelta(minutes=self.METARupdateInterval_edit.value())
		settings.FPL_update_interval = timedelta(minutes=self.FPLupdateInterval_edit.value())
		
		## Solo and teacher session types
		settings.solo_aircraft_types = [s for s in self.soloAircraftTypes_edit.toPlainText().split('\n') if s != '']
		settings.solo_restrict_to_available_liveries = self.restrictAirlineChoiceToLiveries_tickBox.isChecked()
		settings.solo_prefer_entry_exit_ADs = self.preferEntryExitAirports_tickBox.isChecked()
		settings.sphinx_acoustic_model_dir = self.sphinxAcousticModel_edit.text()
		settings.audio_input_device_index = self.audioDeviceIndex_edit.value()
		
		signals.systemSettingsChanged.emit()
		self.accept()




# =================================
#
#       S O L O   S Y S T E M
#
# =================================


class SoloSessionSettingsDialog(QDialog, Ui_soloSessionSettingsDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.cpdlcConnections_label.setEnabled(settings.controller_pilot_data_link)
		self.cpdlcConnections_widget.setEnabled(settings.controller_pilot_data_link)
		self.airportMode_groupBox.setEnabled(env.airport_data != None)
		self.voiceInstr_off_radioButton.setChecked(True) # sets a defult; auto-excludes if voice instr selected below
		self.readBack_off_radioButton.setChecked(True) # sets a defult; auto-excludes if other selection below
		self.voiceInstr_on_radioButton.setEnabled(speech_recognition_available)
		self.readBack_voice_radioButton.setEnabled(speech_synthesis_available)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.fillFromSettings()
		self.buttonBox.accepted.connect(self.storeSettings)
	
	def fillFromSettings(self):
		self.maxAircraftCount_edit.setValue(settings.solo_max_aircraft_count)
		self.minSpawnDelay_seconds_edit.setValue(int(settings.solo_min_spawn_delay.total_seconds()))
		self.maxSpawnDelay_minutes_edit.setValue(int(settings.solo_max_spawn_delay.total_seconds()) / 60)
		self.cpdlcConnectionBalance_edit.setValue(int(100 * settings.solo_CPDLC_balance))
		self.distractorCount_edit.setValue(settings.solo_distracting_traffic_count)
		self.ARRvsDEP_edit.setValue(int(100 * settings.solo_ARRvsDEP_balance))
		self.ILSvsVisual_edit.setValue(int(100 * settings.solo_ILSvsVisual_balance))
		self.soloWeatherChangeInterval_edit.setValue(int(settings.solo_weather_change_interval.total_seconds()) / 60)
		self.voiceInstr_on_radioButton.setChecked(self.voiceInstr_on_radioButton.isEnabled() and settings.solo_voice_instructions)
		self.readBack_wilcoBeep_radioButton.setChecked(settings.solo_wilco_beeps)
		self.readBack_voice_radioButton.setChecked(self.readBack_voice_radioButton.isEnabled() and settings.solo_voice_readback)
	
	def storeSettings(self):
		settings.solo_max_aircraft_count = self.maxAircraftCount_edit.value()
		settings.solo_min_spawn_delay = timedelta(seconds=self.minSpawnDelay_seconds_edit.value())
		settings.solo_max_spawn_delay = timedelta(minutes=self.maxSpawnDelay_minutes_edit.value())
		settings.solo_CPDLC_balance = self.cpdlcConnectionBalance_edit.value() / 100
		settings.solo_distracting_traffic_count = self.distractorCount_edit.value()
		settings.solo_ARRvsDEP_balance = self.ARRvsDEP_edit.value() / 100
		settings.solo_ILSvsVisual_balance = self.ILSvsVisual_edit.value() / 100
		settings.solo_weather_change_interval = timedelta(minutes=self.soloWeatherChangeInterval_edit.value())
		settings.solo_voice_instructions = self.voiceInstr_on_radioButton.isChecked()
		settings.solo_wilco_beeps = self.readBack_wilcoBeep_radioButton.isChecked()
		settings.solo_voice_readback = self.readBack_voice_radioButton.isChecked()
		signals.soloSessionSettingsChanged.emit()
		self.accept()







# =================================
#
#           G E N E R A L
#
# =================================

class QStringListModel_noDropReplacement(QStringListModel):
	def __init__(self, strlst):
		QStringListModel.__init__(self, strlst)
	
	def flags(self, index):
		flags = QStringListModel.flags(self, index)
		if index.isValid():
			flags &= ~Qt.ItemIsDropEnabled
		return flags


class GeneralSettingsDialog(QDialog, Ui_generalSettingsDialog):
	#STATIC:
	last_tab_used = 0
	
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.CPDLC_tab.setEnabled(settings.controller_pilot_data_link)
		self.positionHistoryTraceTime_edit.setMaximum(snapshot_history_size) # limit is one snapshot per second
		self.autoLinkStrip_off_radioButton.setChecked(True) # sets a defult; auto-excludes if different selection below
		self.installEventFilter(RadioKeyEventFilter(self))
		self.fillFromSettings()
		self.settings_tabs.setCurrentIndex(GeneralSettingsDialog.last_tab_used)
		self.addMsgPreset_button.clicked.connect(self.addPresetMessage)
		self.rmMsgPreset_button.clicked.connect(self.removePresetMessage)
		self.buttonBox.accepted.connect(self.storeSettings)
	
	def addPresetMessage(self):
		msg, ok = QInputDialog.getText(self, 'New preset text message', 'Enter message (aliases allowed):')
		if ok:
			self.msg_presets_model.setStringList(self.msg_presets_model.stringList() + [msg])
	
	def removePresetMessage(self):
		ilst = self.messageList_view.selectedIndexes()
		if ilst != []:
			self.msg_presets_model.removeRow(ilst[0].row())

	def fillFromSettings(self):
		self.routeVectWarnings_tickBox.setChecked(settings.strip_route_vect_warnings)
		self.cpdlcStatusIntegrationToStrips_tickBox.setChecked(settings.strip_CPDLC_integration)
		self.confirmHandovers_tickBox.setChecked(settings.confirm_handovers)
		self.confirmLossyStripReleases_tickBox.setChecked(settings.confirm_lossy_strip_releases)
		self.confirmLinkedStripDeletions_tickBox.setChecked(settings.confirm_linked_strip_deletions)
		self.autoFillStripFromXPDR_tickBox.setChecked(settings.strip_autofill_on_ACFT_link)
		self.autoFillStripFromFPL_tickBox.setChecked(settings.strip_autofill_on_FPL_link)
		self.autoFillStripBeforeHandovers_tickBox.setChecked(settings.strip_autofill_before_handovers)
		self.autoLinkStrip_identModeS_radioButton.setChecked(settings.strip_autolink_on_ident)
		self.autoLinkStrip_identAll_radioButton.setChecked(settings.strip_autolink_on_ident and settings.strip_autolink_include_modeC)
		
		self.positionHistoryTraceTime_edit.setValue(int(settings.radar_contact_trace_time.total_seconds()))
		self.toleratedInvisibleSweeps_edit.setValue(int(settings.invisible_blips_before_contact_lost))
		if settings.radar_tag_FL_at_bottom:
			self.flSpeedLine3_radioButton.setChecked(True)
		else:
			self.flSpeedLine2_radioButton.setChecked(True)
		self.interpretXpdrFl_tickBox.setChecked(settings.radar_tag_interpret_XPDR_FL)
		
		self.headingTolerance_edit.setValue(settings.heading_tolerance)
		self.altitudeTolerance_edit.setValue(settings.altitude_tolerance)
		self.speedTolerance_edit.setValue(settings.speed_tolerance)
		self.conflictWarningTime_edit.setValue(int(settings.route_conflict_anticipation.total_seconds()) // 60)
		self.trafficConsidered_select.setCurrentIndex(settings.route_conflict_traffic)
		
		self.cpdlcSuggestVectors_tickBox.setChecked(settings.CPDLC_suggest_vector_instructions)
		self.cpdlcTransferDataAuthority_tickBox.setChecked(settings.CPDLC_authority_transfers)
		self.cpdlcSuggestInstrIfNoTransfer_tickBox.setChecked(settings.CPDLC_suggest_handover_instructions)
		self.cpdlcRaiseWindows_tickBox.setChecked(settings.CPDLC_raises_windows)
		self.cpdlcCloseWindows_tickBox.setChecked(settings.CPDLC_closes_windows)
		if settings.CPDLC_ACK_timeout == None:
			self.cpdlcTimeout_edit.setValue(0)
		else:
			self.cpdlcTimeout_edit.setValue(int(settings.CPDLC_ACK_timeout.total_seconds()))
		
		if settings.text_chat_history_time == None:
			self.textChatMessagesVisibleTime_edit.setValue(0)
		else:
			self.textChatMessagesVisibleTime_edit.setValue(int(settings.text_chat_history_time.total_seconds()) // 60)
		self.msg_presets_model = QStringListModel_noDropReplacement(settings.preset_chat_messages)
		self.messageList_view.setModel(self.msg_presets_model)
		self.autoAtcChatWindowPopUp_tickBox.setChecked(settings.private_ATC_msg_auto_raise)
		self.notifyGeneralChatRoomMsg_tickBox.setChecked(settings.ATC_chatroom_msg_notifications)
	
	def storeSettings(self):
		GeneralSettingsDialog.last_tab_used = self.settings_tabs.currentIndex()
		
		settings.strip_route_vect_warnings = self.routeVectWarnings_tickBox.isChecked()
		settings.strip_CPDLC_integration = self.cpdlcStatusIntegrationToStrips_tickBox.isChecked()
		settings.confirm_handovers = self.confirmHandovers_tickBox.isChecked()
		settings.confirm_lossy_strip_releases = self.confirmLossyStripReleases_tickBox.isChecked()
		settings.confirm_linked_strip_deletions = self.confirmLinkedStripDeletions_tickBox.isChecked()
		settings.strip_autofill_on_ACFT_link = self.autoFillStripFromXPDR_tickBox.isChecked()
		settings.strip_autofill_on_FPL_link = self.autoFillStripFromFPL_tickBox.isChecked()
		settings.strip_autofill_before_handovers = self.autoFillStripBeforeHandovers_tickBox.isChecked()
		settings.strip_autolink_on_ident = not self.autoLinkStrip_off_radioButton.isChecked()
		settings.strip_autolink_include_modeC = self.autoLinkStrip_identAll_radioButton.isChecked()
		
		settings.radar_contact_trace_time = timedelta(seconds=self.positionHistoryTraceTime_edit.value())
		settings.invisible_blips_before_contact_lost = self.toleratedInvisibleSweeps_edit.value()
		settings.radar_tag_FL_at_bottom = self.flSpeedLine3_radioButton.isChecked()
		settings.radar_tag_interpret_XPDR_FL = self.interpretXpdrFl_tickBox.isChecked()
		
		settings.heading_tolerance = self.headingTolerance_edit.value()
		settings.altitude_tolerance = self.altitudeTolerance_edit.value()
		settings.speed_tolerance = self.speedTolerance_edit.value()
		settings.route_conflict_anticipation = timedelta(minutes=self.conflictWarningTime_edit.value())
		settings.route_conflict_traffic = self.trafficConsidered_select.currentIndex()
		
		settings.CPDLC_suggest_vector_instructions = self.cpdlcSuggestVectors_tickBox.isChecked()
		settings.CPDLC_authority_transfers = self.cpdlcTransferDataAuthority_tickBox.isChecked()
		settings.CPDLC_suggest_handover_instructions = self.cpdlcSuggestInstrIfNoTransfer_tickBox.isChecked()
		settings.CPDLC_raises_windows = self.cpdlcRaiseWindows_tickBox.isChecked()
		settings.CPDLC_closes_windows = self.cpdlcCloseWindows_tickBox.isChecked()
		if self.cpdlcTimeout_edit.value() == 0:
			settings.CPDLC_ACK_timeout = None
		else:
			settings.CPDLC_ACK_timeout = timedelta(seconds=self.cpdlcTimeout_edit.value())
		
		if self.textChatMessagesVisibleTime_edit.value() == 0:
			settings.text_chat_history_time = None
		else:
			settings.text_chat_history_time = timedelta(minutes=self.textChatMessagesVisibleTime_edit.value())
		settings.preset_chat_messages = self.msg_presets_model.stringList()
		settings.private_ATC_msg_auto_raise = self.autoAtcChatWindowPopUp_tickBox.isChecked()
		settings.ATC_chatroom_msg_notifications = self.notifyGeneralChatRoomMsg_tickBox.isChecked()
		
		signals.generalSettingsChanged.emit()
		self.accept()






# =================================
#
#           L O C A L
#
# =================================

class LocalSettingsDialog(QDialog, Ui_localSettingsDialog):
	#STATIC:
	last_tab_used = 0
	
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.setWindowTitle('%s location settings - %s' % (('CTR' if env.airport_data == None else 'AD'), settings.location_code))
		self.range_group_boxes = [self.range1_groupBox, self.range2_groupBox, self.range3_groupBox, self.range4_groupBox]
		self.range_name_edits = [self.range1_name_edit, self.range2_name_edit, self.range3_name_edit, self.range4_name_edit]
		self.range_lo_edits = [self.range1_lo_edit, self.range2_lo_edit, self.range3_lo_edit, self.range4_lo_edit]
		self.range_hi_edits = [self.range1_hi_edit, self.range2_hi_edit, self.range3_hi_edit, self.range4_hi_edit]
		self.range_col_edits = [self.range1_colourPicker, self.range2_colourPicker, self.range3_colourPicker, self.range4_colourPicker]
		if env.airport_data == None: # CTR session
			self.stripPrinter_groupBox.setEnabled(False)
			self.settings_tabs.removeTab(self.settings_tabs.indexOf(self.AD_tab))
			self.spawnCTR_minFL_edit.valueChanged.connect(self.spawnCTR_minFL_valueChanged)
			self.spawnCTR_maxFL_edit.valueChanged.connect(self.spawnCTR_maxFL_valueChanged)
		else: # AD session
			self.runway_tabs = QTabWidget(self)
			self.runway_tabs.setTabShape(QTabWidget.Triangular)
			self.runway_tabs.setTabPosition(QTabWidget.South)
			for rwy in env.airport_data.allRunways(sortByName=True):
				self.runway_tabs.addTab(RunwayParametersWidget(self, rwy), rwy.name)
			if env.airport_data.transition_altitude != None:
				self.transitionAltitude_edit.setEnabled(False)
				self.transitionAltitude_edit.setToolTip('Fixed by airport data')
			self.settings_tabs.insertTab(0, self.runway_tabs, 'Runways')
			self.settings_tabs.removeTab(self.settings_tabs.indexOf(self.CTR_tab))
			self.spawnAPP_minFL_edit.valueChanged.connect(self.spawnAPP_minFL_valueChanged)
			self.spawnAPP_maxFL_edit.valueChanged.connect(self.spawnAPP_maxFL_valueChanged)
			self.TWRrangeCeiling_edit.valueChanged.connect(self.TWRrangeCeiling_valueChanged)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.fillFromSettings()
		self.settings_tabs.setCurrentIndex(GeneralSettingsDialog.last_tab_used)
		self.buttonBox.accepted.connect(self.storeSettings)
	
	def spawnAPP_minFL_valueChanged(self, v):
		if v < self.TWRrangeCeiling_edit.value():
			self.TWRrangeCeiling_edit.setValue(v)
		if v > self.spawnAPP_maxFL_edit.value():
			self.spawnAPP_maxFL_edit.setValue(v)
	
	def spawnAPP_maxFL_valueChanged(self, v):
		if v < self.spawnAPP_minFL_edit.value():
			self.spawnAPP_minFL_edit.setValue(v)
	
	def TWRrangeCeiling_valueChanged(self, v):
		if v > self.spawnAPP_minFL_edit.value():
			self.spawnAPP_minFL_edit.setValue(v)
	
	def spawnCTR_minFL_valueChanged(self, v):
		if v > self.spawnCTR_maxFL_edit.value():
			self.spawnCTR_maxFL_edit.setValue(v)
	
	def spawnCTR_maxFL_valueChanged(self, v):
		if v < self.spawnCTR_minFL_edit.value():
			self.spawnCTR_minFL_edit.setValue(v)
		
	def selectSemiCircRule(self, rule):
		radio_button = {
				SemiCircRule.OFF: self.semiCircRule_radioButton_off,
				SemiCircRule.E_W: self.semiCircRule_radioButton_EW,
				SemiCircRule.N_S: self.semiCircRule_radioButton_NS
			}[rule]
		radio_button.setChecked(True)
		
	def selectedSemiCircRule(self):
		if self.semiCircRule_radioButton_off.isChecked(): return SemiCircRule.OFF
		elif self.semiCircRule_radioButton_EW.isChecked(): return SemiCircRule.E_W
		elif self.semiCircRule_radioButton_NS.isChecked(): return SemiCircRule.N_S

	def fillFromSettings(self):
		# Equipment tab
		self.capability_noSSR_radioButton.setChecked(settings.SSR_mode_capability == '0')
		self.capability_modeA_radioButton.setChecked(settings.SSR_mode_capability == 'A')
		self.capability_modeC_radioButton.setChecked(settings.SSR_mode_capability == 'C')
		self.capability_modeS_radioButton.setChecked(settings.SSR_mode_capability == 'S')
		self.radarHorizontalRange_edit.setValue(settings.radar_range)
		self.radarFloor_edit.setValue(settings.radar_signal_floor_level)
		self.radarUpdateInterval_edit.setValue(int(settings.radar_sweep_interval.total_seconds()))
		self.radioDirectionFinding_tickBox.setChecked(settings.radio_direction_finding)
		self.cpdlc_tickBox.setChecked(settings.controller_pilot_data_link)
		self.stripAutoPrint_DEP_tickBox.setChecked(settings.auto_print_strips_include_DEP)
		self.stripAutoPrint_ARR_tickBox.setChecked(settings.auto_print_strips_include_ARR)
		self.stripAutoPrint_ifrOnly_tickBox.setChecked(settings.auto_print_strips_IFR_only)
		self.stripAutoPrint_leadTime_edit.setValue(int(settings.auto_print_strips_anticipation.total_seconds()) // 60)
		# Rules tab
		self.horizontalSeparation_edit.setValue(settings.horizontal_separation)
		self.verticalSeparation_edit.setValue(settings.vertical_separation)
		self.conflictWarningFloorFL_edit.setValue(settings.conflict_warning_floor_FL)
		self.transitionAltitude_edit.setValue(env.transitionAltitude())
		self.uncontrolledVFRcode_edit.setValue(settings.uncontrolled_VFR_XPDR_code)
		self.radioName_edit.setText(settings.location_radio_name)
		# XPDR ranges tab
		for i, rng in enumerate(settings.XPDR_assignment_ranges[:len(self.range_group_boxes)]):
			self.range_group_boxes[i].setChecked(True)
			self.range_name_edits[i].setText(rng.name)
			self.range_lo_edits[i].setValue(rng.lo)
			self.range_hi_edits[i].setValue(rng.hi)
			self.range_col_edits[i].setChoice(rng.col)
		# Other settings tab
		if env.airport_data == None: # CTR mode
			self.spawnCTR_minFL_edit.setValue(settings.solo_CTR_floor_FL)
			self.spawnCTR_maxFL_edit.setValue(settings.solo_CTR_ceiling_FL)
			self.CTRrangeDistance_edit.setValue(settings.solo_CTR_range_dist)
			self.routingPoints_edit.setText(' '.join(settings.solo_CTR_routing_points))
			self.selectSemiCircRule(settings.solo_CTR_semi_circular_rule)
		else: # AD mode
			self.spawnAPP_minFL_edit.setValue(settings.solo_APP_ceiling_FL_min)
			self.spawnAPP_maxFL_edit.setValue(settings.solo_APP_ceiling_FL_max)
			self.TWRrangeDistance_edit.setValue(settings.solo_TWR_range_dist)
			self.TWRrangeCeiling_edit.setValue(settings.solo_TWR_ceiling_FL)
			self.initialClimb_edit.setText(settings.solo_initial_climb_reading)
		self.atisCustomAppendix_edit.setPlainText(settings.ATIS_custom_appendix)
	
	def storeSettings(self):
		## CHECK SETTINGS FIRST
		try:
			new_ranges = []
			for i in range(len(self.range_group_boxes)):
				if self.range_group_boxes[i].isChecked():
					name = self.range_name_edits[i].text()
					if any(rng.name == name for rng in new_ranges):
						raise ValueError('Duplicate range name')
					colour = self.range_col_edits[i].getChoice()
					new_ranges.append(XpdrAssignmentRange(name, self.range_lo_edits[i].value(), self.range_hi_edits[i].value(), colour))
		except ValueError as err:
			QMessageBox.critical(self, 'Assignment range error', str(err))
			return
		if env.airport_data == None:
			try:
				bad = next(p for p in self.routingPoints_edit.text().split() if len(env.navpoints.findAll(code=p)) != 1)
				QMessageBox.critical(self, 'Invalid entry', 'Unknown navpoint or navpoint not unique: %s' % bad)
				return
			except StopIteration:
				pass # no bad navpoints
		else:
			try:
				alt_reading = StdPressureAlt.reformatReading(self.initialClimb_edit.text())
			except ValueError:
				QMessageBox.critical(self, 'Invalid entry', 'Could not read altitude or level for default initial climb.')
				return
		
		## ALL SETTINGS OK. Save them and accept the dialog.
		GeneralSettingsDialog.last_tab_used = self.settings_tabs.currentIndex()
		
		if env.airport_data != None:
			for i in range(self.runway_tabs.count()):
				self.runway_tabs.widget(i).applyToRWY()
		
		settings.SSR_mode_capability = '0' if self.capability_noSSR_radioButton.isChecked() \
				else 'A' if self.capability_modeA_radioButton.isChecked() \
				else 'C' if self.capability_modeC_radioButton.isChecked() else 'S'
		settings.radar_range = self.radarHorizontalRange_edit.value()
		settings.radar_signal_floor_level = self.radarFloor_edit.value()
		settings.radar_sweep_interval = timedelta(seconds=self.radarUpdateInterval_edit.value())
		settings.radio_direction_finding = self.radioDirectionFinding_tickBox.isChecked()
		settings.controller_pilot_data_link = self.cpdlc_tickBox.isChecked()
		settings.auto_print_strips_include_DEP = self.stripAutoPrint_DEP_tickBox.isChecked()
		settings.auto_print_strips_include_ARR = self.stripAutoPrint_ARR_tickBox.isChecked()
		settings.auto_print_strips_IFR_only = self.stripAutoPrint_ifrOnly_tickBox.isChecked()
		settings.auto_print_strips_anticipation = timedelta(minutes=self.stripAutoPrint_leadTime_edit.value())
		
		settings.vertical_separation = self.verticalSeparation_edit.value()
		settings.conflict_warning_floor_FL = self.conflictWarningFloorFL_edit.value()
		settings.location_radio_name = self.radioName_edit.text()
		settings.transition_altitude = self.transitionAltitude_edit.value() # NOTE useless if a TA is set in apt.dat
		settings.uncontrolled_VFR_XPDR_code = self.uncontrolledVFRcode_edit.value()
		settings.horizontal_separation = self.horizontalSeparation_edit.value()
		
		settings.XPDR_assignment_ranges = new_ranges
		
		if env.airport_data == None: # CTR mode
			settings.solo_CTR_floor_FL = self.spawnCTR_minFL_edit.value()
			settings.solo_CTR_ceiling_FL = self.spawnCTR_maxFL_edit.value()
			settings.solo_CTR_range_dist = self.CTRrangeDistance_edit.value()
			settings.solo_CTR_routing_points = self.routingPoints_edit.text().split()
			settings.solo_CTR_semi_circular_rule = self.selectedSemiCircRule()
		else: # AD mode
			settings.solo_APP_ceiling_FL_min = self.spawnAPP_minFL_edit.value() // 10 * 10
			settings.solo_APP_ceiling_FL_max = ((self.spawnAPP_maxFL_edit.value() - 1) // 10 + 1) * 10
			settings.solo_TWR_range_dist = self.TWRrangeDistance_edit.value()
			settings.solo_TWR_ceiling_FL = self.TWRrangeCeiling_edit.value()
			settings.solo_initial_climb_reading = alt_reading
		settings.ATIS_custom_appendix = self.atisCustomAppendix_edit.toPlainText()
		
		signals.localSettingsChanged.emit()
		self.accept()




