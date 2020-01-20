
from PyQt5.QtWidgets import QWidget, QInputDialog, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from ui.cpdlcPanel import Ui_cpdlcPanel
from ui.cpdlcConnection import Ui_cpdlcConnection

from data.util import pop_all
from data.comms import CpdlcMessage
from data.instruction import Instruction
from models.cpdlc import CpdlcHistoryFilterModel, ConnectionStatus

from session.env import env
from session.config import settings
from session.manager import teacher_callsign, SessionType, CpdlcAuthorityTransferFailed

from gui.misc import selection, signals, IconFile
from gui.widgets.miscWidgets import RadioKeyEventFilter
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

# -------------------------------


class CpdlcPanel(QWidget, Ui_cpdlcPanel):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.last_selected_callsign = '' # will filter all ACFT
		self.filter_model = CpdlcHistoryFilterModel(self, env.cpdlc)
		self.connections_tableView.setModel(self.filter_model)
		self.child_windows = [] # CpdlcConnectionWidget list
		# Signals
		self.connections_tableView.doubleClicked.connect(self.openFilteredDataLinkWindow)
		self.liveConnections_radioButton.toggled.connect(self.filter_model.setLiveFilter)
		self.historyWith_radioButton.toggled.connect(self.updateCallsignFilter)
		signals.cpdlcAcftConnected.connect(self._checkAutoRaise)
		signals.cpdlcMessageReceived.connect(self.msgReceived)
		signals.cpdlcProblem.connect(self._checkAutoRaise)
		signals.cpdlcWindowRequest.connect(self.openCallsignLatestDataLinkWindow)
		signals.localSettingsChanged.connect(self.localSettingsChanged) # in case CPDLC equipment is turned off
		signals.selectionChanged.connect(self.updateCallsignFilter)
		signals.sessionEnded.connect(self.closeChildWindows)
		signals.slowClockTick.connect(self.deleteClosedWindows)
		# Finish set-up
		self.liveConnections_radioButton.setChecked(True)
	
	def openDataLinkWindow(self, data_link_model):
		try:
			window = next(w for w in self.child_windows if w.model() is data_link_model and not w.closed())
		except StopIteration:
			window = CpdlcConnectionWidget(self, data_link_model)
			window.setWindowIcon(QIcon(IconFile.panel_CPDLC))
			window.setWindowFlags(Qt.Window)
			window.installEventFilter(RadioKeyEventFilter(self))
			self.child_windows.append(window)
		window.show()
		window.raise_()
	
	def openFilteredDataLinkWindow(self, index):
		self.openDataLinkWindow(env.cpdlc.dataLinkOnRow(self.filter_model.mapToSource(index).row()))
	
	def openCallsignLatestDataLinkWindow(self, callsign):
		link = env.cpdlc.latestDataLink(callsign)
		if link != None:
			self.openDataLinkWindow(link)
	
	def _checkAutoRaise(self, callsign):
		if settings.CPDLC_raises_windows:
			self.openCallsignLatestDataLinkWindow(callsign)
	
	def msgReceived(self, sender, msg):
		if msg.type() != CpdlcMessage.ACK:
			self._checkAutoRaise(sender)
	
	def localSettingsChanged(self):
		if not settings.controller_pilot_data_link:
			env.cpdlc.endAllDataLinks()
	
	def updateCallsignFilter(self):
		sel = selection.selectedCallsign()
		if sel != None:
			self.last_selected_callsign = sel
			self.historyWith_radioButton.setText('History with ' + sel)
		if self.historyWith_radioButton.isChecked():
			self.filter_model.setCallsignFilter(self.last_selected_callsign)
		else: # user wants to filter on live status (accept all callsigns)
			self.filter_model.setCallsignFilter(None)
	
	def closeChildWindows(self):
		for w in self.child_windows:
			w.close()
		self.deleteClosedWindows() # WARNING statusChanged might still be connected but no dialogue is still live
	
	def deleteClosedWindows(self):
		for w in pop_all(self.child_windows, CpdlcConnectionWidget.closed):
			w.deleteLater()







class CpdlcConnectionWidget(QWidget, Ui_cpdlcConnection):
	def __init__(self, parent, data_link_model):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.delete_me = False
		self.resolveProblems_button.setIcon(QIcon(IconFile.button_clear))
		self.transfer_button.setVisible(settings.session_manager.session_type != SessionType.TEACHER) # ACFT POV; cannot transfer oneself
		self.sendMsg_frame.setVisible(settings.session_manager.session_type != SessionType.SOLO)
		self.data_link_model = data_link_model
		self.messages_tableView.setModel(self.data_link_model)
		self.data_link_model.rowsInserted.connect(self.messages_tableView.scrollToBottom)
		self.data_link_model.statusChanged.connect(self._updateDisplay)
		self.data_link_model.statusChanged.connect(self._checkAutoClose)
		# buttons/actions
		self.transfer_button.clicked.connect(self.transferDataAuthority)
		self.disconnect_button.clicked.connect(self.terminateLink)
		self.resolveProblems_button.clicked.connect(self.resolveProblems)
		self.ACK_button.clicked.connect(self.ackButtonClicked)
		self.reject_button.clicked.connect(self.rejectClicked)
		self.sendFreeText_button.clicked.connect(self.sendFreeTextMessage)
		self._updateDisplay()

	def closeEvent(self, event):
		self.delete_me = True
	
	def model(self):
		return self.data_link_model
	
	def closed(self):
		return self.delete_me
	
	def _updateDisplay(self):
		self.acftCallsign_info.setText(self.data_link_model.acftCallsign())
		self.status_info.setText(self.data_link_model.statusStr()) # would window stay open for 24+ hours?
		self.transfer_button.setEnabled(self.data_link_model.isLive())
		self.disconnect_button.setEnabled(self.data_link_model.isLive())
		self.resolveProblems_button.setEnabled(self.data_link_model.status() == ConnectionStatus.PROBLEM)
		self.sendMsg_frame.setEnabled(self.data_link_model.isLive())
	
	def _checkAutoClose(self):
		if settings.CPDLC_closes_windows:
			if not self.data_link_model.isLive() and self.data_link_model.status() == ConnectionStatus.OK:
				self.close()
	
	def transferDataAuthority(self, list_index): # NOTE button hidden to teacher
		items = env.ATCs.knownATCs(lambda atc: \
				settings.session_manager.session_type != SessionType.STUDENT or atc.callsign != teacher_callsign)
		if len(items) > 0:
			item, ok = QInputDialog.getItem(self, 'Transfer data authority', 'Select ATC:', items, editable=False)
			if ok:
				try:
					settings.session_manager.transferCpdlcAuthority(self.data_link_model.acftCallsign(), item)
				except CpdlcAuthorityTransferFailed as err:
					QMessageBox.critical(self, 'CPDLC transfer failure', str(err))
	
	def terminateLink(self):
		cs = self.data_link_model.acftCallsign()
		if yesNo_question(self, 'Terminate data link', 'Disconnect current data link with %s.' % cs, 'OK?'):
			settings.session_manager.disconnectCpdlc(cs)
	
	def resolveProblems(self):
		self.data_link_model.resolveProblems()
	
	def ackButtonClicked(self):
		if self.data_link_model.msgCount() > 0:
			last_msg = self.data_link_model.lastMsg()
			if not last_msg.isFromMe() and last_msg.type() == CpdlcMessage.REQUEST:
				try:
					instr = Instruction.fromEncodedStr(last_msg.contents())
				except ValueError:
					QMessageBox.critical(self, 'CPDLC comm error', 'Unable to decode request. Mismatching program versions?')
				else:
					selection.writeStripAssignment(instr)
					msg = CpdlcMessage(True, CpdlcMessage.INSTR, contents=instr.encodeToStr())
					settings.session_manager.sendCpdlcMsg(self.data_link_model.acftCallsign(), msg)
				return
		msg = CpdlcMessage(True, CpdlcMessage.ACK)
		settings.session_manager.sendCpdlcMsg(self.data_link_model.acftCallsign(), msg)
	
	def rejectClicked(self):
		txt, ok = QInputDialog.getText(self, 'CPDLC reject message', 'Reason/message (optional):')
		if ok:
			msg = CpdlcMessage(True, CpdlcMessage.REJECT, contents=txt)
			settings.session_manager.sendCpdlcMsg(self.data_link_model.acftCallsign(), msg)
	
	def sendFreeTextMessage(self):
		msg = CpdlcMessage(True, CpdlcMessage.FREE_TEXT, contents=self.freeText_edit.text())
		self.freeText_edit.clear()
		settings.session_manager.sendCpdlcMsg(self.data_link_model.acftCallsign(), msg)

