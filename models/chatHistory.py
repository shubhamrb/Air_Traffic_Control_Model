
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex

from session.config import settings
from data.utc import now, rel_datetime_str


# ---------- Constants ----------

# -------------------------------




# =============================================== #

#                     MODELS                      #

# =============================================== #




class TextChatHistoryModel(QAbstractTableModel):
	columns = ['Time', 'From', 'Message']

	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.msg_list = []

	def rowCount(self, parent=None):
		return len(self.msg_list)

	def columnCount(self, parent):
		return len(TextChatHistoryModel.columns)

	def data(self, index, role):
		if role == Qt.DisplayRole:
			chat_line = self.messageOnRow(index.row())
			col = index.column()
			if col == 0:
				return rel_datetime_str(chat_line.timeStamp(), seconds=True)
			if col == 1:
				return chat_line.sender()
			if col == 2:
				return chat_line.txtMsg()

	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return TextChatHistoryModel.columns[section]
	
	def messageOnRow(self, index):
		return self.msg_list[index]
	
	def privateChatCallsigns(self):
		return set(msg.recipient() if msg.isFromMe() else msg.sender() for msg in self.msg_list if msg.isPrivate())
	
	def addChatMessage(self, msg):
		position = self.rowCount()
		self.beginInsertRows(QModelIndex(), position, position)
		self.msg_list.insert(position, msg)
		self.endInsertRows()
		return True
	
	def clearHistory(self):
		self.beginResetModel()
		self.msg_list.clear()
		self.endResetModel()







class RadioTextChatFilterModel(QSortFilterProxyModel):
	def __init__(self, base_model, parent=None):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(base_model)
		self.hidden_senders = []
	
	def messageOnRow(self, filtered_list_row):
		source_index = self.mapToSource(self.index(filtered_list_row, 0)).row()
		return self.sourceModel().messageOnRow(source_index)
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		msg = self.sourceModel().messageOnRow(sourceRow)
		return msg.sender() not in self.hidden_senders \
			and (settings.text_chat_history_time == None or now() - msg.timeStamp() <= settings.text_chat_history_time)
	
	def blacklistSender(self, callsign):
		self.hidden_senders.append(callsign)
		self.invalidateFilter()
	
	def blacklist(self):
		return self.hidden_senders
	
	def clearBlacklist(self):
		self.hidden_senders.clear()
		self.invalidateFilter()





class AtcChatFilterModel(QSortFilterProxyModel):
	def __init__(self, base_model, parent=None):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(base_model)
		self.selected_ATC = None # None for public messages (general chat room)
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		return self.filterAcceptsMessage(self.sourceModel().messageOnRow(sourceRow))
	
	def filterAcceptsMessage(self, msg):
		if msg.isPrivate():
			return msg.involves(self.selected_ATC)
		else:
			return self.selected_ATC == None
	
	def filterPublic(self):
		self.selected_ATC = None
		self.invalidateFilter()
	
	def filterInvolving(self, callsign):
		self.selected_ATC = callsign
		self.invalidateFilter()
	
	def filteredATC(self):
		'''
		returns None if currently selecting non-private messages
		'''
		return self.selected_ATC


