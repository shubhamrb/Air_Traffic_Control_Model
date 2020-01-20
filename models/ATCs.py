

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox

from session.config import settings
from session.env import env
from session.manager import SessionType, HandoverBlocked

from data.coords import dist_str
from data.strip import strip_mime_type, sent_to_detail
from data.instruction import Instruction

from gui.misc import signals, selection, IconFile
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

nearby_dist_threshold = .1 # NM

# -------------------------------

# [[*]] WARNING [[*]]
# dataChanged.emit instructions in QAbstractTableModels cause error
# "QObject::connect: Cannot queue arguments of type 'QVector<int>'"
# if connected across threads, because of optional argument "roles".
# See also: https://bugreports.qt.io/browse/QTBUG-46517
# The work-around here is to use "refreshViews" from main thread after
# data changes have been made. Less efficient but OK as lists are small.



class ATC:
	def __init__(self, callsign):
		self.callsign = callsign
		self.social_name = None
		self.position = None
		self.frequency = None
	
	def toolTipText(self):
		txt = ''
		if self.social_name != None:
			txt += self.social_name + '\n'
		txt += 'Position: '
		if self.position == None:
			txt += 'unknown'
		else:
			distance = env.radarPos().distanceTo(self.position)
			if distance < nearby_dist_threshold:
				txt += 'nearby'
			else:
				txt += '%s°, %s' % (env.radarPos().headingTo(self.position).readTrue(), dist_str(distance))
		return txt



class AtcTableModel(QAbstractTableModel):
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.gui = parent
		self.ATCs = [] # list of ATC objects
		self.unread_private_msg_from = set() # set of callsigns who have sent ATC messages since their last view switch
		self.textChat_received_icon = QIcon(IconFile.panel_atcChat)

	def columnCount(self, parent=QModelIndex()):
		return 2

	def rowCount(self, parent=QModelIndex()):
		return len(self.ATCs)
		
	def data(self, index, role):
		atc = self.ATCs[index.row()]
		col = index.column()
		
		if role == Qt.DisplayRole:
			if col == 0:
				return atc.callsign
			elif col == 1:
				if atc.frequency != None:
					return str(atc.frequency)
		
		elif role == Qt.DecorationRole:
			if col == 0:
				if atc.callsign in self.unread_private_msg_from:
					return self.textChat_received_icon
		
		elif role == Qt.ToolTipRole:
			return atc.toolTipText()
	
	def flags(self, index):
		flags = Qt.ItemIsEnabled
		if index.isValid() and index.column() == 0:
			flags |= Qt.ItemIsDropEnabled
		return flags
	
	
	## ACCESS FUNCTIONS
	
	def knownATCs(self, pred=None):
		'''
		"pred" filters list; default = all ATCs.
		'''
		return [atc.callsign for atc in self.ATCs if pred == None or pred(atc)]
	
	def atcOnRow(self, row):
		return self.ATCs[row]
	
	def markedUnreadPMs(self):
		return list(self.unread_private_msg_from)
	
	# by callsign, raise KeyError if not in model
	def getATC(self, cs):
		try:
			return next(atc for atc in self.ATCs if atc.callsign == cs)
		except StopIteration:
			raise KeyError(cs)
	
	def handoverInstructionTo(self, atc):
		try:
			frq = self.getATC(atc).frequency
		except KeyError:
			frq = None
		return Instruction(Instruction.HAND_OVER, arg=(atc, frq))
	
	
	## UPDATE FUNCTIONS
	
	def markUnreadPMs(self, atc):
		self.unread_private_msg_from.add(atc)
	
	def unmarkUnreadPMs(self, atc):
		try:
			self.unread_private_msg_from.remove(atc)
		except KeyError:
			pass
	
	def updateATC(self, callsign, pos, name, frq):
		'''
		Updates an ATC if already present; adds it otherwise with the given details.
		'''
		try:
			row, atc = next((i, atc) for i, atc in enumerate(self.ATCs) if atc.callsign == callsign)
		except StopIteration:
			atc = ATC(callsign)
			row = len(self.ATCs)
			self.beginInsertRows(QModelIndex(), row, row)
			self.ATCs.append(atc)
			signals.newATC.emit(callsign)
			self.endInsertRows()
		atc.social_name = name
		atc.position = pos
		atc.frequency = frq
		# FUTURE enable? [[*]] self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))
	
	def removeATC(self, callsign):
		try:
			row = next(i for i, atc in enumerate(self.ATCs) if atc.callsign == callsign)
			self.beginRemoveRows(QModelIndex(), row, row)
			self.unmarkUnreadPMs(callsign)
			del self.ATCs[row]
			self.endRemoveRows()
		except StopIteration:
			raise KeyError(callsign)
	
	def clear(self):
		self.beginResetModel()
		self.ATCs.clear()
		self.unread_private_msg_from.clear()
		self.endResetModel()
	
	def refreshViews(self): # [[*]]
		self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
	
	
	## DRAG AND DROP STUFF
	
	def supportedDropActions(self):
		return Qt.MoveAction
	
	def mimeTypes(self):
		return [strip_mime_type]
	
	def dropMimeData(self, mime, drop_action, row, column, parent):
		if drop_action == Qt.MoveAction and mime.hasFormat(strip_mime_type):
			strip = env.strips.fromMimeDez(mime)
			atc_callsign = self.ATCs[parent.row()].callsign
			if not settings.confirm_handovers or settings.session_manager.session_type == SessionType.TEACHER or \
					yesNo_question(self.gui, 'Confirm handover', 'You are about to send your strip to %s.' % atc_callsign, 'Confirm?'):
				if settings.strip_autofill_before_handovers:
					strip.fillFromXPDR(ovr=False)
					strip.fillFromFPL(ovr=False)
				try:
					settings.session_manager.stripDroppedOnATC(strip, atc_callsign)
				except HandoverBlocked as err:
					if not err.silent:
						QMessageBox.critical(self.gui, 'Handover aborted', str(err))
				else:
					selection.deselect()
					strip.writeDetail(sent_to_detail, atc_callsign)
					if settings.session_manager.session_type != SessionType.TEACHER:
						strip.linkAircraft(None)
						strip.linkFPL(None)
						env.strips.removeStrip(strip)
						env.discarded_strips.addStrip(strip)
					return True
		return False

