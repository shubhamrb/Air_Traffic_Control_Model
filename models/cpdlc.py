
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QSortFilterProxyModel, QModelIndex

from data.utc import now, rel_datetime_str
from data.comms import CpdlcMessage

from session.config import settings
from session.manager import SessionType

from gui.misc import signals
from gui.graphics.miscGraphics import coloured_square_icon


# ---------- Constants ----------

# -------------------------------


# ================================================ #

#                  FULL  HISTORY                   #

# ================================================ #

class CpdlcHistoryModel(QAbstractTableModel):
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.connection_history = []  # CpdlcConnectionModel list
		self.live = {}  # callsign -> index of current connection in history
		self.gui = parent
	
	def _dataLinkStatusChanged(self, row):
		self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [Qt.DecorationRole])
		self.dataChanged.emit(self.index(row, 1), self.index(row, 1))
	
	def updateAckStatuses(self):
		for dm in self.connection_history:
			if not dm.timed_out:
				dm.checkAckTimeout()
	
	
	## ACCESS
	
	def dataLinkOnRow(self, row):
		try:
			return self.connection_history[row]
		except IndexError:
			return None
	
	def isConnected(self, callsign):
		return callsign in self.live
	
	def currentDataLink(self, callsign):
		try:
			return self.dataLinkOnRow(self.live[callsign])
		except KeyError:
			return None
	
	def latestDataLink(self, callsign):
		return next((dl for dl in reversed(self.connection_history) if dl.acftCallsign() == callsign), None)
	
	
	## MODIFICATION
	
	def beginDataLink(self, acft_callsign, atc_callsign, transferFrom=None): # should only be called if accepting logons
		if self.isConnected(acft_callsign):
			print('WARNING: Ignored CPDLC init call; callsign %s already connected.' % acft_callsign)
		else:
			conn_row = len(self.connection_history)
			self.beginInsertRows(QModelIndex(), conn_row, conn_row)
			atc_pov = settings.session_manager.session_type != SessionType.TEACHER
			dm = CpdlcConnectionModel(self.gui, atc_pov, acft_callsign, atc_callsign, xfr=transferFrom)
			dm.statusChanged.connect(lambda row=conn_row: self._dataLinkStatusChanged(row))
			self.connection_history.append(dm)
			self.live[acft_callsign] = conn_row
			self.endInsertRows()
			signals.cpdlcAcftConnected.emit(acft_callsign)
	
	def endDataLink(self, acft_callsign, transferTo=None):
		try:
			conn_row = self.live.pop(acft_callsign)
		except KeyError:
			print('WARNING: Ignored CPDLC termination; callsign %s not connected.' % acft_callsign)
		else:
			self.connection_history[conn_row].terminate(xfr=transferTo)
			self.dataChanged.emit(self.index(conn_row, 0), self.index(conn_row, 1))
			signals.cpdlcAcftDisconnected.emit(acft_callsign)
	
	def endAllDataLinks(self):
		for cs in list(self.live): # list to avoid changing dict size during iteration on keys
			self.endDataLink(cs)
	
	def clearHistory(self):
		self.beginResetModel()
		self.connection_history.clear()
		self.endResetModel()
	
	
	## MODEL STUFF
	
	def rowCount(self, parent):
		return len(self.connection_history)

	def columnCount(self, parent):
		return 2

	def data(self, index, role):
		data_link = self.connection_history[index.row()]
		col = index.column()
		if role == Qt.DisplayRole:
			if col == 0: # callsign
				return data_link.acftCallsign()
			elif col == 1: # status
				return data_link.statusStr()
		elif role == Qt.DecorationRole:
			if col == 0:
				status = data_link.status()
				if data_link.isLive() or status != ConnectionStatus.OK:
					deco_colour = {
							ConnectionStatus.OK: Qt.darkGreen,
							ConnectionStatus.PROBLEM: Qt.red,
							ConnectionStatus.EXPECTING: Qt.yellow
						}[status]
					return coloured_square_icon(deco_colour)





class CpdlcHistoryFilterModel(QSortFilterProxyModel):
	def __init__(self, parent, src_model):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(src_model)
		self.callsign_filter = None
		self.live_filter = False
	
	def filterAcceptsColumn(self, sourceCol, sourceParent):
		return True
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		data_link = self.sourceModel().dataLinkOnRow(sourceRow)
		return (not self.live_filter or data_link.isLive()) \
			and (self.callsign_filter == None or self.callsign_filter == data_link.acftCallsign())
	
	def setLiveFilter(self, b):
		self.live_filter = b
		self.invalidateFilter()
	
	def setCallsignFilter(self, callsign):
		self.callsign_filter = callsign
		self.invalidateFilter()
	
	














# ================================================ #

#                 SINGLE DATA LINK                 #

# ================================================ #

class ConnectionStatus:
	OK, PROBLEM, EXPECTING = range(3)


class CpdlcConnectionModel(QAbstractTableModel):
	statusChanged = pyqtSignal()
	
	def __init__(self, parent, atc_pov, acft_callsign, atc_callsign, xfr=None):
		QAbstractTableModel.__init__(self, parent)
		self.atc_pov = atc_pov
		self.acft_callsign = acft_callsign
		self.data_authority = atc_callsign
		self.initiator = xfr # Transferring ATC, or None if initiated by ACFT
		self.messages = []
		self.connect_time = now()
		self.disconnect_time = None
		self.transferred_to = None
		self.expecting = False # True if either party is expecting an answer
		self.timed_out = False # True if other party took too long to answer
		self.problems = {} # int msg index -> str problem to resolve
	
	def checkAckTimeout(self):
		if settings.CPDLC_ACK_timeout != None and self.expecting:
			last_msg = self.lastMsg()
			if last_msg.isFromMe() and now() - last_msg.timeStamp() >= settings.CPDLC_ACK_timeout:
				self.timed_out = True
				self.statusChanged.emit()
				signals.cpdlcProblem.emit(self.acftCallsign(), 'Answer timed out')
	
	def _markProblem(self, problem_row, problem_descr):
		self.problems[problem_row] = problem_descr
		signals.cpdlcProblem.emit(self.acftCallsign(), problem_descr)
	
	
	## ACCESS
	
	def lastMsg(self):
		return self.messages[-1]
	
	def msgCount(self):
		return len(self.messages)
	
	def acftCallsign(self):
		return self.acft_callsign
	
	def dataAuthority(self):
		return self.data_authority
	
	def isLive(self):
		return self.disconnect_time == None
	
	def connectionTime(self):
		return self.connect_time
	
	def disconnectionTime(self):
		return self.disconnect_time
	
	def status(self):
		if self.timed_out or len(self.problems) > 0:
			return ConnectionStatus.PROBLEM
		elif self.isLive() and self.expecting:
			return ConnectionStatus.EXPECTING
		else:
			return ConnectionStatus.OK
	
	def statusStr(self):
		if len(self.problems) > 0:
			return 'Problems to resolve'
		if not self.isLive():
			return 'Terminated' if self.transferred_to == None else 'Transferred'
		if self.timed_out:
			return 'Expected answer timed out'
		if self.expecting: # implies message list not empty
			return 'Waiting for answer...' if self.lastMsg().isFromMe() else 'Please answer...'
		# Status OK and still live
		return 'New connection' if self.msgCount() == 0 else 'Connected'
	
	
	## MODIFICATION
	
	def appendMessage(self, msg):
		if not self.isLive():
			print('WARNING: CPDLC message appended to terminated data link.')
		n = self.msgCount()
		t = msg.type()
		self.beginInsertRows(QModelIndex(), n, n)
		self.messages.append(msg)
		self.endInsertRows()
		# update status attributes
		if not msg.isFromMe(): # need a signal
			if t == CpdlcMessage.REJECT:
				self._markProblem(n, 'Rejected')
			else:
				signals.cpdlcMessageReceived.emit(self.acftCallsign(), msg)
		self.timed_out = False
		self.expecting = t in [CpdlcMessage.REQUEST, CpdlcMessage.INSTR, CpdlcMessage.FREE_TEXT]
		self.statusChanged.emit()
	
	def terminate(self, xfr=None):
		if self.expecting: # should imply message count > 0
			problem_row = self.msgCount() - 1
			self.timed_out = False
			self.expecting = False
			self._markProblem(problem_row, 'Expected answer never received')
			self.dataChanged.emit(self.index(problem_row, 2), self.index(problem_row, 2))
		if self.isLive():
			self.disconnect_time = now()
			self.transferred_to = xfr
			self.statusChanged.emit()
		else:
			print('WARNING: CPDLC connection already terminated.')
	
	def resolveProblems(self):
		self.problems.clear()
		self.dataChanged.emit(self.index(0, 3), self.index(self.msgCount() - 1, 3))
		self.statusChanged.emit()
	
	
	## MODEL STUFF
	
	def rowCount(self, parent=QModelIndex()):
		return self.msgCount() + (1 if self.isLive() else 2)

	def columnCount(self, parent=QModelIndex()):
		return 4  # normal message row: time stamp, message type, contents, remark/problem

	def data(self, index, role):
		row = index.row()
		col = index.column()
		if role == Qt.DisplayRole:
			if row == 0: ## First row of a connection
				if col == 0:
					return rel_datetime_str(self.connectionTime(), seconds=True)
				elif col == 1 and self.initiator != None:
					return 'XFR'
				elif col == 2:
					if self.atc_pov:
						return 'ACFT log-on' if self.initiator == None else 'Received from %s' % self.initiator
					else: # ACFT point of view
						return 'Logged on' if self.initiator == None else '%s → %s' % (self.initiator, self.dataAuthority())
			elif row == self.rowCount() - 1 and not self.isLive(): ## Last row of a terminated or transferred connection
				if col == 0:
					return rel_datetime_str(self.disconnectionTime(), seconds=True)
				elif col == 1 and self.transferred_to != None:
					return 'XFR'
				elif col == 2:
					return 'Terminated' if self.transferred_to == None else 'Transferred to %s' % self.transferred_to
			else: ## Regular message row
				imsg = row - 1
				msg = self.messages[imsg]
				if col == 0:
					return rel_datetime_str(msg.timeStamp(), seconds=True)
				elif col == 1:
					prefix = '↓↑'[self.atc_pov] + '  ' if msg.isFromMe() else ''
					return prefix + CpdlcMessage.type2str(msg.type())
				elif col == 2:
					return msg.contents()
				elif col == 3:
					if imsg in self.problems:
						return self.problems[imsg]
					elif imsg == self.msgCount() - 1 and self.expecting:
						return self.statusStr()

