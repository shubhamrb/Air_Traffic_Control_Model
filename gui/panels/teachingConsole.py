from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import QWidget, QMessageBox, QInputDialog
from PyQt5.QtGui import QIcon
from ui.teachingConsole import Ui_teachingConsole

from data.util import some
from data.params import Heading
from data.utc import now, rel_datetime_str
from data.comms import CommFrequency, CpdlcMessage
from data.instruction import Instruction
from data.strip import assigned_SQ_detail
from data.weather import mkWeather, gust_diff_threshold

from session.config import settings
from session.env import env
from session.manager import SessionType, student_callsign, teacher_callsign

from gui.misc import IconFile, signals, selection
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

# -------------------------------


def valid_new_ATC_name(name):
	return name not in env.ATCs.knownATCs() and name not in ['', teacher_callsign, student_callsign]



# =============================================== #

#                     MODELS                      #

# =============================================== #


class TeachingAtcModel(QAbstractTableModel):
	columns = ['Callsign', 'Frequency']
	
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.ATCs = [] # callsign list
	
	def rowCount(self, parent=None):
		return len(self.ATCs)
	
	def columnCount(self, parent):
		return len(TeachingAtcModel.columns)
	
	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return TeachingAtcModel.columns[section]
	
	def data(self, index, role):
		atc = self.ATCs[index.row()]
		col = index.column()
		if role == Qt.DisplayRole:
			if col == 0: # callsign
				return atc
			elif col == 1: # frequency
				frq = env.ATCs.getATC(atc).frequency
				if frq != None:
					return str(frq)
	
	def setData(self, index, value, role=Qt.EditRole):
		col = index.column()
		row = index.row()
		atc = self.ATCs[row]
		value = value.strip()
		if col == 0 and valid_new_ATC_name(value):
			frq = env.ATCs.getATC(atc).frequency
			env.ATCs.updateATC(value, None, None, frq) # adds new ATC to env
			env.ATCs.removeATC(atc) # removes old ATC from env
			self.ATCs[row] = value
		elif col == 1:
			try:
				env.ATCs.updateATC(atc, None, None, (None if value == '' else CommFrequency(value)))
			except ValueError:
				return False
		self.dataChanged.emit(index, index)
		settings.session_manager.sendATCs() # updates distant student list
		return True
	
	def addATC(self, atc):
		position = self.rowCount()
		env.ATCs.updateATC(atc, None, None, None) # adds new ATC to env
		self.beginInsertRows(QModelIndex(), position, position)
		self.ATCs.append(atc)
		self.endInsertRows()
		settings.session_manager.sendATCs() # updates distant student list
		return True
	
	def removeAtcOnRow(self, row):
		self.beginRemoveRows(QModelIndex(), row, row)
		env.ATCs.removeATC(self.ATCs.pop(row))
		self.endRemoveRows()
		settings.session_manager.sendATCs() # updates distant student list
		return True







class SituationSnapshotModel(QAbstractTableModel):
	columns = ['Situation', 'Traffic']
	
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.snapshots = [] # (situation, time, name) list

	def rowCount(self, parent=None):
		return len(self.snapshots)

	def columnCount(self, parent):
		return len(SituationSnapshotModel.columns)

	def flags(self, index):
		basic_flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
		return basic_flags | Qt.ItemIsEditable if index.column() == 0 else basic_flags

	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return SituationSnapshotModel.columns[section]

	def data(self, index, role):
		sit, t, name = self.snapshots[index.row()] # situation, time, name
		col = index.column()
		if role == Qt.DisplayRole:
			if col == 0:
				return some(name, 'Saved %s' % rel_datetime_str(t, seconds=True))
			elif col == 1:
				spawned = len([acft for acft in sit if acft[4]])
				return '%d + %d' % (spawned, len(sit) - spawned)
		elif role == Qt.ToolTipRole:
			if col == 0:
				return 'Saved %s' % rel_datetime_str(t, seconds=True) if name != None else 'Double-click to name this entry.'
			elif col == 1:
				return 'Spawned + unspawned count'

	def setData(self, index, value, role=Qt.EditRole):
		if index.column() == 0:
			row = index.row()
			sit, t, old_name = self.snapshots[row]
			self.snapshots[row] = sit, t, (None if value == '' else value)
			self.dataChanged.emit(index, index)
			return True
		else:
			return False

	def situationOnRow(self, row):
		return self.snapshots[row][0]
	
	def addSnapshot(self, snapshot):
		position = self.rowCount()
		self.beginInsertRows(QModelIndex(), position, position)
		self.snapshots.insert(position, (snapshot, now(), None))
		self.endInsertRows()
		return True
	
	def removeSnapshot(self, row):
		self.beginRemoveRows(QModelIndex(), row, row)
		del self.snapshots[row]
		self.endRemoveRows()
		return True











# ============================================== #

#                  THE CONSOLE                   #

# ============================================== #


class TeachingConsole(QWidget, Ui_teachingConsole):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.onTouchDown_groupBox.setVisible(env.airport_data != None)
		self.setWindowIcon(QIcon(IconFile.panel_teaching))
		self.removeATC_button.setIcon(QIcon(IconFile.button_bin))
		self.removeSituation_button.setIcon(QIcon(IconFile.button_bin))
		self.ATCs_tableModel = TeachingAtcModel(self)
		self.ATCs_tableView.setModel(self.ATCs_tableModel)
		self.situationSnapshots_tableModel = SituationSnapshotModel(self)
		self.situationSnapshots_tableView.setModel(self.situationSnapshots_tableModel)
		self.windHdg_radioButton.setText('%s°' % self._windDialHdg().readTrue())
		self.setEnabled(False)
		self.ATC_neighbours = {} # atc callsign -> frq or None
		# ACFT callsign/status section
		self.spawn_button.clicked.connect(self.spawnSelectedACFT)
		self.freezeACFT_button.toggled.connect(self.freezeSelectedACFT)
		self.kill_button.clicked.connect(self.killSelectedACFT)
		# ACFT XPDR section
		self.xpdrMode_select.currentIndexChanged.connect(self.setXpdrMode)
		self.squat_tickBox.toggled.connect(self.toggleSquat)
		self.xpdrCode_select.codeChanged.connect(self.setXpdrCode)
		self.squawkVFR_button.clicked.connect(lambda: self.xpdrCode_select.setSQ(settings.uncontrolled_VFR_XPDR_code))
		self.xpdrIdent_tickBox.toggled.connect(self.toggleXpdrIdent)
		self.pushSQtoStrip_button.clicked.connect(self.SQcodeToStrip)
		# ACFT CPDLC section
		self.cpdlcLogOn_button.clicked.connect(self.cpdlcLogOn)
		self.cpdlcTransfer_button.clicked.connect(self.cpdlcTransfer)
		self.cpdlcVectorRequest_toggle.toggled.connect(self.cpdlcVectorRequestToggled)
		self.showDataLinkWindow_button.clicked.connect(self.openCpdlcWindow)
		# ACFT "on touch-down" section
		self.onTouchDown_touchAndGo_radioButton.toggled.connect(self.toggleTouchAndGo)
		self.onTouchDown_skidOffRwy_radioButton.toggled.connect(self.toggleSkidOffRwy)
		# Weather section
		self.windHdg_dial.valueChanged.connect(lambda: self.windHdg_radioButton.setText('%s°' % self._windDialHdg().readTrue()))
		self.windSpeed_edit.valueChanged.connect(lambda spd: self.windGusts_edit.setMinimum(spd + gust_diff_threshold))
		self.visibility_edit.editingFinished.connect(self._roundVisibilityValue)
		self.cloudLayer_select.currentIndexChanged.connect(self._updateCloudLayerHeightWidgets)
		self.cloudLayerHeight_edit.valueChanged.connect(self._updateCloudLayerHeightWidgets)
		self.applyWeather_button.clicked.connect(self.applyWeather)
		# ATC section
		self.addATC_button.clicked.connect(self.addATC)
		self.removeATC_button.clicked.connect(self.removeATC)
		self.ATCs_tableView.selectionModel().selectionChanged.connect(self._updateAtcButtons)
		# Snapshots section
		self.snapshotSituation_button.clicked.connect(self.snapshotSituation)
		self.restoreSituation_button.clicked.connect(self.restoreSituation)
		self.removeSituation_button.clicked.connect(self.removeSituation)
		self.situationSnapshots_tableView.selectionModel().selectionChanged.connect(self._updateSnapshotsButtons)
		# Misc.
		self.touchDownWithoutClearance_tickBox.toggled.connect(self.toggleAcftTouchDownWithoutClearance)
		self.pauseSim_button.toggled.connect(self.togglePause)
		signals.localSettingsChanged.connect(self.xpdrCode_select.updateXPDRranges)
		signals.sessionStarted.connect(self.sessionHasStarted)
		signals.sessionEnded.connect(self.sessionHasEnded)
		self.last_session_type = None
	
	def _windDialHdg(self):
		return Heading(5 * self.windHdg_dial.value(), True)
	
	def sessionHasStarted(self):
		self.last_session_type = settings.session_manager.session_type
		if self.last_session_type == SessionType.TEACHER:
			settings.teacher_ACFT_requesting_CPDLC_vectors = None
			self.setEnabled(True)
			self.show()
			signals.selectionChanged.connect(self.updateAcftSection)
			signals.cpdlcAcftConnected.connect(self.updateAcftSection)
			signals.cpdlcAcftDisconnected.connect(self.updateAcftSection)
			self.updateAcftSection()
			self._updateCloudLayerHeightWidgets()
			self._updateAtcButtons()
			self._updateSnapshotsButtons()
			self.applyWeather() # initialises the weather for the session
	
	def sessionHasEnded(self):
		if self.last_session_type == SessionType.TEACHER:
			signals.selectionChanged.disconnect(self.updateAcftSection)
			signals.cpdlcAcftConnected.disconnect(self.updateAcftSection)
			signals.cpdlcAcftDisconnected.disconnect(self.updateAcftSection)
			self.setEnabled(False)
			self.hide()
	
	def updateAcftSection(self):
		ai_acft = selection.acft
		if ai_acft == None:
			self.selectedAircraft_box.setEnabled(False)
			self.selectedCallsign_info.setText('')
			self.spawn_button.setVisible(False)
			self.cpdlc_stackedWidget.setCurrentWidget(self.cpdlc_connect_page) # to hide any thick "capturing" message while disabled
		else:
			# callsign section
			self.selectedAircraft_box.setEnabled(True)
			self.selectedCallsign_info.setText(ai_acft.identifier if ai_acft.spawned else '%s (unspawned)' % ai_acft.identifier)
			self.spawn_button.setVisible(not ai_acft.spawned)
			self.freezeACFT_button.setChecked(ai_acft.frozen)
			# XPDR box
			self.xpdrMode_select.setCurrentIndex('0ACS'.index(ai_acft.params.XPDR_mode))
			self.squat_tickBox.setEnabled(ai_acft.params.XPDR_mode == 'S')
			self.squat_tickBox.setChecked(ai_acft.mode_S_squats)
			self.xpdrCode_select.setSQ(ai_acft.params.XPDR_code)
			self.xpdrIdent_tickBox.setChecked(ai_acft.params.XPDR_idents)
			# CPDLC box
			self.cpdlc_stackedWidget.setCurrentWidget(self.cpdlc_connected_page if env.cpdlc.isConnected(ai_acft.identifier) else self.cpdlc_connect_page)
			if ai_acft.identifier == settings.teacher_ACFT_requesting_CPDLC_vectors and env.cpdlc.isConnected(ai_acft.identifier):
				self.cpdlcVectorRequest_toggle.setChecked(True)
			else:
				self.cpdlcVectorRequest_toggle.setChecked(False)
				settings.teacher_ACFT_requesting_CPDLC_vectors = None # resets the button toggle
			self._updateCpdlcVectorRequestInfoLabel()
			latest = env.cpdlc.latestDataLink(ai_acft.identifier)
			if latest == None:
				self.showDataLinkWindow_button.setEnabled(False)
				self.showDataLinkWindow_button.setText('Never connected')
			else:
				self.showDataLinkWindow_button.setEnabled(True)
				self.showDataLinkWindow_button.setText('Open (connected)' if latest.isLive() else 'Open')
			# "On touch-down" box
			if ai_acft.skid_off_RWY_on_LDG:
				self.onTouchDown_skidOffRwy_radioButton.setChecked(True)
			elif ai_acft.touch_and_go_on_LDG:
				self.onTouchDown_touchAndGo_radioButton.setChecked(True)
			else:
				self.onTouchDown_land_radioButton.setChecked(True)
	
	def _updateCpdlcVectorRequestInfoLabel(self):
		self.cpdlcVectorRequest_info.setText('Capturing...' if self.cpdlcVectorRequest_toggle.isChecked() else '')
	
	def _roundVisibilityValue(self):
		self.visibility_edit.setValue((self.visibility_edit.value() + 50) // 100 * 100)
	
	def _updateCloudLayerHeightWidgets(self):
		self.cloudLayerHeight_edit.setEnabled(self.cloudLayer_select.currentIndex() != 0)
		self.cloudLayerHeight_edit.setPrefix(max(0, 3 - len(str(self.cloudLayerHeight_edit.value()))) * '0')
	
	def _updateAtcButtons(self):
		self.removeATC_button.setEnabled(len(self.ATCs_tableView.selectionModel().selectedRows()) == 1)
	
	def _updateSnapshotsButtons(self):
		one_selected = len(self.situationSnapshots_tableView.selectionModel().selectedRows()) == 1
		self.restoreSituation_button.setEnabled(one_selected)
		self.removeSituation_button.setEnabled(one_selected)
	
	
	## ACFT status actions
	
	def spawnSelectedACFT(self):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.spawned = True
		self.updateAcftSection()
	
	def freezeSelectedACFT(self, toggle):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.frozen = toggle
		self.updateAcftSection()
	
	def killSelectedACFT(self):
		acft = selection.acft
		if acft != None:
			selection.deselect()
			settings.session_manager.killAircraft(acft)
			env.radar.scan()
			self.updateAcftSection()
	
	
	## ACFT transponder actions
	
	def setXpdrMode(self, drop_down_index):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.params.XPDR_mode = '0ACS'[drop_down_index]
		self.updateAcftSection()
	
	def SQcodeToStrip(self):
		strip = selection.strip
		if strip != None:
			strip.writeDetail(assigned_SQ_detail, self.xpdrCode_select.getSQ())
			signals.stripInfoChanged.emit()
	
	def setXpdrCode(self):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.params.XPDR_code = self.xpdrCode_select.getSQ()
	
	def toggleSquat(self, toggle):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.mode_S_squats = toggle
	
	def toggleXpdrIdent(self, toggle):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.params.XPDR_idents = toggle
	
	
	## ACFT CPDLC actions
	
	def cpdlcLogOn(self):
		if selection.acft != None:
			settings.session_manager.requestCpdlcConnection(selection.acft.identifier)
	
	def cpdlcTransfer(self):
		if selection.acft != None:
			items = env.ATCs.knownATCs(lambda atc: atc.callsign != student_callsign)
			if len(items) == 0:
				QMessageBox.critical(self, 'CPDLC transfer to student', 'No ATCs to transfer data authority from.')
			else:
				item, ok = QInputDialog.getItem(self, 'CPDLC transfer to student',
						'Transfer data authority to student from:', items, editable=False)
				if ok:
					settings.session_manager.transferCpdlcAuthority(selection.acft.identifier, item)
	
	def cpdlcVectorRequestToggled(self, b):
		if b:
			if selection.acft != None:
				settings.teacher_ACFT_requesting_CPDLC_vectors = selection.acft.identifier
		else:
			settings.teacher_ACFT_requesting_CPDLC_vectors = None
		self._updateCpdlcVectorRequestInfoLabel()
	
	def openCpdlcWindow(self):
		if selection.acft != None:
			signals.cpdlcWindowRequest.emit(selection.acft.identifier)
	
	
	## ACFT "on touch-down" actions
	
	def toggleTouchAndGo(self, b):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.touch_and_go_on_LDG = b
	
	def toggleSkidOffRwy(self, b):
		ai_acft = selection.acft
		if ai_acft != None:
			ai_acft.skid_off_RWY_on_LDG = b
	
	
	## WEATHER actions
	
	def applyWeather(self):
		if self.windCalm_radioButton.isChecked():
			wind_str = '00000KT'
		else:
			wind_str = 'VRB' if self.windVRB_radioButton.isChecked() else self._windDialHdg().readTrue() # main dir chars
			wind_str += '%02d' % self.windSpeed_edit.value() # main speed chars
			if self.windGusts_edit.isEnabled():
				wind_str += 'G%02d' % self.windGusts_edit.value()
			wind_str += 'KT'
			if self.windHdgRange_edit.isEnabled():
				w = self._windDialHdg().trueAngle()
				v = self.windHdgRange_edit.value()
				wind_str += ' %sV%s' % (Heading(w - v, True).readTrue(), Heading(w + v, True).readTrue())
		visibility = self.visibility_edit.value()
		if visibility == self.visibility_edit.minimum(): # special 10-km value
			visibility = 10000
		if self.cloudLayer_select.currentIndex() == 0:
			cl = 'NSC'
		else:
			cl = '%s%03d' % (self.cloudLayer_select.currentText(), self.cloudLayerHeight_edit.value())
		weather = mkWeather(settings.primary_METAR_station, wind=wind_str, vis=visibility, clouds=cl, qnh=self.QNH_edit.value())
		settings.session_manager.setWeather(weather)
	
	
	## ATC actions

	def addATC(self):
		txt, ok = QInputDialog.getText(self, 'Add ATC to list', 'ATC callsign:')
		if ok:
			atc = txt.strip()
			if valid_new_ATC_name(atc):
				self.ATCs_tableModel.addATC(atc)
			else:
				QMessageBox.critical(self, 'Add ATC to list', 'Invalid, duplicate or reserved name.')
	
	def removeATC(self):
		try:
			index = self.ATCs_tableView.selectedIndexes()[0]
		except IndexError:
			print('No ATC selected to remove.')
		else:
			self.ATCs_tableModel.removeAtcOnRow(index.row())
	
	
	## Situation snapshot actions
	
	def snapshotSituation(self):
		self.situationSnapshots_tableModel.addSnapshot(settings.session_manager.situationSnapshot())
	
	def restoreSituation(self):
		try:
			index = self.situationSnapshots_tableView.selectedIndexes()[0]
		except IndexError:
			print('No situation selected to restore.')
		else:
			snapshot = self.situationSnapshots_tableModel.situationOnRow(index.row())
			settings.session_manager.restoreSituation(snapshot)
			env.radar.scan()
	
	def removeSituation(self):
		try:
			index = self.situationSnapshots_tableView.selectedIndexes()[0]
		except IndexError:
			print('No situation selected to remove.')
		else:
			if yesNo_question(self, 'Remove situation', 'This will make selected situation unavailable.', 'Are you sure?'):
				self.situationSnapshots_tableModel.removeSnapshot(index.row())
	
	
	## Misc. session actions

	def toggleAcftTouchDownWithoutClearance(self, b):
		settings.teacher_ACFT_touch_down_without_clearance = b
	
	def togglePause(self, toggle):
		if toggle:
			settings.session_manager.pauseSession()
		else:
			settings.session_manager.resumeSession()
	
