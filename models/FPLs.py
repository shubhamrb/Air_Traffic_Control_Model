
from datetime import timedelta

from PyQt5.QtCore import Qt, QModelIndex, QAbstractTableModel

from data.util import pop_all, some
from data.fpl import FPL
from data.utc import now

from session.config import settings
from gui.graphics.miscGraphics import coloured_square_icon


# ---------- Constants ----------

FPL_outdated_delay = timedelta(hours=2)

# -------------------------------




class FlightPlanModel(QAbstractTableModel):
	column_headers = ['Status', 'Callsign', 'Flight', 'Time']

	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.FPL_list = []
	
	def refreshViews(self): # [[*]]
		self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return FlightPlanModel.column_headers[section]

	def rowCount(self, parent=QModelIndex()):
		return 0 if parent.isValid() else len(self.FPL_list)

	def columnCount(self, parent=QModelIndex()):
		return 0 if parent.isValid() else len(FlightPlanModel.column_headers)

	def data(self, index, role):
		fpl = self.FPL_list[index.row()]
		col = index.column()
		if role == Qt.DisplayRole:
			if col == 0:
				if fpl.existsOnline() and fpl.needsUpload(): # not in sync with online version
					return '!!'
			elif col == 1:
				return some(fpl[FPL.CALLSIGN], '?')
			elif col == 2:
				return fpl.shortDescr_AD()
			elif col == 3:
				return fpl.shortDescr_time()
		
		elif role == Qt.DecorationRole:
			if col == 0:
				if fpl.existsOnline():
					status = fpl.status()
					if status == FPL.FILED:
						dep = fpl[FPL.TIME_OF_DEP]
						if dep != None and now() > dep + FPL_outdated_delay: # outdated
							colour = settings.colour('FPL_filed_outdated')
						else:
							colour = settings.colour('FPL_filed')
					elif status == FPL.OPEN:
						eta = fpl.ETA()
						if eta == None: # warning
							colour = settings.colour('FPL_open_noETA')
						elif now() > eta: # overdue
							colour = settings.colour('FPL_open_overdue')
						else:
							colour = settings.colour('FPL_open')
					elif status == FPL.CLOSED:
						colour = settings.colour('FPL_closed')
					return coloured_square_icon(colour)
		
		elif role == Qt.ToolTipRole:
			if col == 0:
				if fpl.existsOnline():
					status = fpl.status()
					if status == FPL.FILED:
						dep = fpl[FPL.TIME_OF_DEP]
						txt = 'Outdated' if dep != None and now() > dep + FPL_outdated_delay else 'Filed'
					elif status == FPL.OPEN:
						eta = fpl.ETA()
						if eta == None: # warning
							txt = 'Open, ETA unknown'
						else:
							txt = 'Open'
							minutes_overtime = int(round((now() - eta).total_seconds())) // 60
							if minutes_overtime >= 1:
								txt += ', arrival overdue by %d h %02d min' % (minutes_overtime // 60, minutes_overtime % 60)
					elif status == FPL.CLOSED:
						txt = 'Closed'
					else:
						txt = 'Status N/A'
					if fpl.needsUpload():
						txt += '\n(local changes)'
					return txt
				else:
					return 'Not online'
	
	
	def addFPL(self, fpl):
		position = self.rowCount()
		self.beginInsertRows(QModelIndex(), position, position)
		self.FPL_list.insert(position, fpl)
		self.endInsertRows()
		return True
	
	def removeFPL(self, fpl):
		row = next(i for i in range(len(self.FPL_list)) if self.FPL_list[i] is fpl)
		self.beginRemoveRows(QModelIndex(), row, row)
		del self.FPL_list[row]
		self.endRemoveRows()
		return True
	
	def clearFPLs(self, pred=None):
		self.beginResetModel()
		if pred == None:
			self.FPL_list.clear()
		else:
			pop_all(self.FPL_list, lambda fpl: pred(fpl))
		self.endResetModel()
		return True
	
	def findFPL(self, pred):
		'''
		Returns a flight plan satisfying pred, and its index.
		Raises StopIteration is none is found.
		'''
		return next((fpl, i) for i, fpl in enumerate(self.FPL_list) if pred(fpl)) # or StopIteration
	
	def findAll(self, pred=None):
		'''
		Returns a list of the flight plans satisfying pred, or all if None.
		'''
		if pred == None:
			return self.FPL_list[:]
		else:
			return [fpl for fpl in self.FPL_list if pred(fpl)]
	
	def FPL(self, index):
		return self.FPL_list[index]


