
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtWidgets import QWidget, QInputDialog, QMenu, QAction, QMessageBox, QCompleter

from ui.radioTextChat import Ui_radioTextChatPanel
from ui.atcTextChat import Ui_atcTextChatPanel

from data.util import some
from data.comms import ChatMessage, replace_text_aliases

from session.env import env
from session.config import settings
from session.manager import SessionType, student_callsign, teacher_callsign

from models.chatHistory import TextChatHistoryModel, RadioTextChatFilterModel, AtcChatFilterModel

from gui.misc import selection, signals
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

text_snip_separator = '|'

# -------------------------------




# =============================================== #

#                 RADIO TEXT CHAT                 #

# =============================================== #


def process_text_chat_line(full_line, value_error_if_missing):
	message = full_line.split(text_snip_separator, maxsplit=1)[-1]
	return replace_text_aliases(message, selection, value_error_if_missing)



class ChatCompleterPopupEventFilter(QObject):
	def __init__(self, on_return_pressed, parent=None):
		QObject.__init__(self, parent)
		self.on_return_pressed = on_return_pressed

	def eventFilter(self, popup_menu, event): # reimplementing
		if event.type() == QEvent.KeyPress and event.key() in [Qt.Key_Return, Qt.Key_Enter]:
			self.on_return_pressed()
			popup_menu.hide()
			return True
		return False



class RadioTextChatPanel(QWidget, Ui_radioTextChatPanel):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.radioChatHistory_baseModel = TextChatHistoryModel(parent=self)
		self.chatHistory_filteredModel = RadioTextChatFilterModel(self.radioChatHistory_baseModel, parent=self)
		self.chatHistory_view.setModel(self.chatHistory_filteredModel)
		self.updatePresetMessages()
		self.chatLine_input.completer().setCompletionMode(QCompleter.PopupCompletion)
		self.chatLine_input.completer().setFilterMode(Qt.MatchContains)
		self.chatLine_input.completer().popup().installEventFilter(ChatCompleterPopupEventFilter(self.sendChatLine, parent=self))
		# Build "opts" menu
		self.clearMessageHistory_action = QAction('Clear message history', self)
		self.blacklistAsSender_action = QAction('Blacklist recipient', self)
		self.showBlacklistedSenders_action = QAction('Show blacklisted senders', self)
		self.clearBlacklist_action = QAction('Clear blacklist', self)
		checkMsgReplacements_action = QAction('Check message replacements', self)
		opts_menu = QMenu()
		opts_menu.addAction(self.clearMessageHistory_action)
		opts_menu.addSeparator()
		opts_menu.addAction(self.blacklistAsSender_action)
		opts_menu.addAction(self.showBlacklistedSenders_action)
		opts_menu.addAction(self.clearBlacklist_action)
		opts_menu.addSeparator()
		opts_menu.addAction(checkMsgReplacements_action)
		self.menu_button.setMenu(opts_menu)
		self.blacklistAsSender_action.setEnabled(False)
		self.clearBlacklist_action.setEnabled(False)
		# Signal connections
		checkMsgReplacements_action.triggered.connect(lambda: self.checkMsgReplacements('Check/edit message'))
		self.clearMessageHistory_action.triggered.connect(self.radioChatHistory_baseModel.clearHistory)
		self.blacklistAsSender_action.triggered.connect(self.blacklistDest)
		self.showBlacklistedSenders_action.triggered.connect(self.showSendersBlacklist)
		self.clearBlacklist_action.triggered.connect(self.chatHistory_filteredModel.clearBlacklist)
		self.clearBlacklist_action.triggered.connect(lambda: self.clearBlacklist_action.setEnabled(False))
		self.dest_combo.editTextChanged.connect(lambda cs: self.blacklistAsSender_action.setEnabled(cs != ''))
		self.send_button.clicked.connect(self.sendChatLine)
		self.chatLine_input.lineEdit().returnPressed.connect(self.sendChatLine)
		self.dest_combo.lineEdit().returnPressed.connect(self.sendChatLine)
		self.chatHistory_view.clicked.connect(self.recallMessage)
		self.resetMessage_button.clicked.connect(self.chatLine_input.clearEditText)
		self.resetMessage_button.clicked.connect(self.chatLine_input.setFocus)
		self.resetDest_button.clicked.connect(self.dest_combo.clearEditText)
		self.resetDest_button.clicked.connect(self.dest_combo.setFocus)
		signals.selectionChanged.connect(self.suggestChatDestFromNewSelection)
		signals.chatInstructionSuggestion.connect(self.fillInstruction)
		signals.incomingRadioChatMsg.connect(self.collectRadioChatMessage)
		signals.generalSettingsChanged.connect(self.updatePresetMessages)
		signals.generalSettingsChanged.connect(self.chatHistory_filteredModel.invalidateFilter)
		signals.slowClockTick.connect(self.updateDestList)
		signals.newATC.connect(self.updateDestList)
		env.radar.newContact.connect(self.updateDestList)
	
	def focusInEvent(self, event):
		QWidget.focusInEvent(self, event)
		self.chatLine_input.setFocus()
		self.chatLine_input.lineEdit().selectAll()
	
	def collectRadioChatMessage(self, msg):
		self.radioChatHistory_baseModel.addChatMessage(msg)
		self.chatHistory_filteredModel.invalidateFilter()
		self.chatHistory_view.scrollToBottom()
	
	def _postChatLine(self, txt):
		if txt == '':
			return # Do not send empty lines
		msg = ChatMessage(settings.session_manager.myCallsign(), txt, recipient=self.dest_combo.currentText())
		if settings.session_manager.isRunning():
			try:
				settings.session_manager.postRadioChatMsg(msg)
				self.collectRadioChatMessage(msg)
				self.chatLine_input.setCurrentIndex(-1)
				self.chatLine_input.clearEditText()
			except ValueError as error:
				QMessageBox.critical(self, 'Text chat error', str(error))
		else:
			QMessageBox.critical(self, 'Text chat error', 'No session running.')
		self.chatLine_input.setFocus()
	
	def sendChatLine(self):
		try:
			self._postChatLine(process_text_chat_line(self.chatLine_input.currentText(), True))
		except ValueError:
			self.checkMsgReplacements('Alias replacements failed!')
	
	def checkMsgReplacements(self, box_title):
		dest = self.dest_combo.currentText()
		txt, ok = QInputDialog.getText(self, box_title, ('Send:' if dest == '' else 'Send to %s:' % dest), \
			text=process_text_chat_line(self.chatLine_input.currentText(), False))
		if ok:
			self._postChatLine(txt)
		else:
			self.chatLine_input.setFocus()
	
	def fillInstruction(self, dest, msg, send):
		self.dest_combo.setEditText(dest)
		self.chatLine_input.setEditText(msg)
		if send:
			self.sendChatLine()
		else:
			self.chatLine_input.setFocus()
	
	def updateDestList(self):
		current_text = self.dest_combo.currentText()
		self.dest_combo.clear()
		self.dest_combo.addItems(['All traffic'] + sorted(list(env.knownCallsigns())))
		self.dest_combo.setEditText(current_text)
	
	def suggestChatDestFromNewSelection(self):
		cs = selection.selectedCallsign()
		if cs != None:
			self.dest_combo.setEditText(cs)
		
	def updatePresetMessages(self):
		self.chatLine_input.clear()
		self.chatLine_input.addItems(settings.preset_chat_messages)
		self.chatLine_input.clearEditText()
	
	def recallMessage(self, index):
		msg = self.chatHistory_filteredModel.messageOnRow(index.row())
		if msg.isFromMe():
			self.dest_combo.setEditText(some(msg.recipient(), ''))
			self.chatLine_input.setEditText(msg.txtOnly())
		else:
			self.dest_combo.setEditText(msg.sender())
		self.chatLine_input.setFocus()
	
	def blacklistDest(self):
		cs = self.dest_combo.currentText()
		if cs != '' and yesNo_question(self, 'Blacklisting from chat', \
					'This will hide past and future messages from %s.' % cs, 'OK?'):
			self.chatHistory_filteredModel.blacklistSender(cs)
			self.clearBlacklist_action.setEnabled(True)
	
	def showSendersBlacklist(self):
		lst = self.chatHistory_filteredModel.blacklist()
		if lst == []:
			txt = 'No blacklisted senders.'
		else:
			txt = 'Blacklisted senders: %s.' % ', '.join(lst)
		QMessageBox.information(self, 'Senders blacklist', txt)




# ================================================ #

#                   ATC TEXT CHAT                  #

# ================================================ #

class AtcTextChatPanel(QWidget, Ui_atcTextChatPanel):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.msgLine_edit.setClearButtonEnabled(True)
		self.atcChatHistory_baseModel = TextChatHistoryModel(parent=self)
		self.chatHistory_filteredModel = AtcChatFilterModel(self.atcChatHistory_baseModel, parent=self)
		self.chatHistory_view.setModel(self.chatHistory_filteredModel)
		self.updateUnreadChats()
		# Signal connections
		self.filterSelect_button.clicked.connect(self.selectFilter)
		self.unreadChats_button.clicked.connect(self.selectUnread)
		self.send_button.clicked.connect(self.sendChatLine)
		self.msgLine_edit.textEdited.connect(self.unmarkUnreadPMsForFilter)
		self.msgLine_edit.returnPressed.connect(self.sendChatLine)
		signals.incomingAtcTextMsg.connect(self.collectAtcTextMessage)
		signals.privateAtcChatRequest.connect(self.switchAtcChatFilter)
		signals.sessionStarted.connect(self.sessionHasStarted)
	
	def sessionHasStarted(self):
		self.atcChatHistory_baseModel.clearHistory()
		if settings.session_manager.session_type == SessionType.TEACHER:
			self.switchAtcChatFilter(student_callsign)
		elif settings.session_manager.session_type == SessionType.STUDENT:
			self.switchAtcChatFilter(teacher_callsign)
		else:
			self.switchAtcChatFilter(None)
	
	def focusInEvent(self, event):
		QWidget.focusInEvent(self, event)
		self.focusMsgInputLine()
	
	def focusMsgInputLine(self):
		self.unmarkUnreadPMsForFilter()
		self.msgLine_edit.setFocus()
		self.msgLine_edit.selectAll()
	
	def updateUnreadChats(self):
		count = len(env.ATCs.markedUnreadPMs())
		self.unreadChats_button.setText('(%d)' % count)
		self.unreadChats_button.setEnabled(count != 0)
	
	def currentChat(self): # returns the callsign to click on to get the current chat panel
		model_filter = self.chatHistory_filteredModel.filteredATC()
		if settings.session_manager.session_type == SessionType.TEACHER and model_filter == teacher_callsign:
			return student_callsign
		else:
			return model_filter
	
	def unmarkUnreadPMsForFilter(self):
		env.ATCs.unmarkUnreadPMs(self.currentChat())
		env.ATCs.refreshViews()
		self.updateUnreadChats()
	
	def collectAtcTextMessage(self, msg):
		self.atcChatHistory_baseModel.addChatMessage(msg)
		self.chatHistory_view.resizeColumnToContents(0)
		self.chatHistory_view.resizeColumnToContents(1)
		if msg.isPrivate():
			if settings.session_manager.session_type == SessionType.TEACHER and not msg.involves(teacher_callsign):
				msg_goes_to = msg.recipient() if msg.sender() == student_callsign else msg.sender()
			else:
				msg_goes_to = msg.recipient() if msg.isFromMe() else msg.sender()
		else:
			msg_goes_to = None
		current_chat = self.currentChat()
		if msg.isPrivate() and not msg.isFromMe(): # we may want to raise panel or mark a PM
			if msg_goes_to != current_chat or not self.msgLine_edit.hasFocus(): # not focused on collecting chat
				if settings.private_ATC_msg_auto_raise:
					signals.privateAtcChatRequest.emit(msg_goes_to) # switches, raises and scrolls table
				else:
					env.ATCs.markUnreadPMs(msg_goes_to)
					env.ATCs.refreshViews()
					self.updateUnreadChats()
		if msg_goes_to == current_chat:
			self.chatHistory_view.scrollToBottom()
	
	def switchAtcChatFilter(self, filter_mode): # None for general chat room; str for callsign private filter
		if filter_mode == None: # select general ATC text chat room
			self.chatHistory_filteredModel.filterPublic()
			self.channel_info.setText('General chat room')
		else: # filter_mode is string callsign of private chat to select
			if settings.session_manager.session_type == SessionType.TEACHER and filter_mode == student_callsign:
				self.chatHistory_filteredModel.filterInvolving(teacher_callsign)
			else:
				self.chatHistory_filteredModel.filterInvolving(filter_mode)
			self.channel_info.setText('Private chat: %s' % filter_mode)
		self.chatHistory_view.scrollToBottom()
		self.focusMsgInputLine()
	
	def selectFilter(self):
		sugg = set(env.ATCs.knownATCs()) | self.atcChatHistory_baseModel.privateChatCallsigns()
		txt, ok = QInputDialog.getItem(self, 'ATC text chat selection',
			'Callsign for private chat;\nblank for general chat room:', [''] + sorted(sugg))
		if ok:
			self.switchAtcChatFilter(None if txt == '' else txt)
	
	def selectUnread(self):
		cs, ok = QInputDialog.getItem(self, 'Unread ATC text chat selection',
			'ATC callsign:', sorted(env.ATCs.markedUnreadPMs()), editable=False)
		if ok:
			self.switchAtcChatFilter(cs)
	
	def sendChatLine(self):
		msg_line = self.msgLine_edit.text()
		if msg_line == '':
			return # Do not send empty lines
		if settings.session_manager.isRunning():
			mouse_atc = self.currentChat()
			if settings.session_manager.session_type == SessionType.TEACHER:
				msg_sender = teacher_callsign if mouse_atc == None or mouse_atc == student_callsign else mouse_atc
				msg_recip = None if mouse_atc == None else student_callsign
			else:
				msg_sender = settings.session_manager.myCallsign()
				msg_recip = mouse_atc
			msg = ChatMessage(msg_sender, msg_line, recipient=msg_recip, private=(msg_recip != None))
			try:
				settings.session_manager.postAtcChatMsg(msg)
			except ValueError as error:
				QMessageBox.critical(self, 'ATC chat error', str(error))
			else:
				self.collectAtcTextMessage(msg)
				self.msgLine_edit.clear()
		else:
			QMessageBox.critical(self, 'Text chat error', 'No session running.')
		self.msgLine_edit.setFocus()


