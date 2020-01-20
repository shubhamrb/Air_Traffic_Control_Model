from PyQt5.QtCore import Qt, QModelIndex, QAbstractListModel, QSortFilterProxyModel
from PyQt5.QtGui import QIcon

from data.util import some, pop_all

from data.utc import now, rel_datetime_str
from data.strip import sent_to_detail, shelved_detail

from gui.misc import IconFile


# ---------- Constants ----------

# -------------------------------


class DiscardedStripModel(QAbstractListModel):
	def __init__(self, parent):
		QAbstractListModel.__init__(self, parent)
		self.discarded_strips = [] # (strip, timestamp) list
		self.handed_over_icon = QIcon(IconFile.panel_ATCs)
		self.deleted_icon = QIcon(IconFile.button_bin)
		self.shelved_icon = QIcon(IconFile.button_shelf)

	def rowCount(self, parent=None):
		return len(self.discarded_strips)
	
	def data(self, index, role):
		strip, timestamp = self.discarded_strips[index.row()]
		if role == Qt.DisplayRole:
			line1 = some(strip.callsign(), '?')
			toATC = strip.lookup(sent_to_detail)
			if toATC == None:
				line2 = 'Shelved ' if strip.lookup(shelved_detail) else 'Deleted '
			else:
				line1 += ' >> ' + toATC
				line2 = 'Sent '
			line2 += rel_datetime_str(timestamp)
			## RETURN
			return '%s\n  %s' % (line1, line2)
		elif role == Qt.DecorationRole:
			if strip.lookup(sent_to_detail) == None: # was deleted or shelved
				return self.shelved_icon if strip.lookup(shelved_detail) else self.deleted_icon
			else: # was handed over
				return self.handed_over_icon
	
	def getStrip(self, row):
		return self.discarded_strips[row][0]
	
	def addStrip(self, strip):
		self.beginInsertRows(QModelIndex(), 0, 0)
		self.discarded_strips.insert(0, (strip, now()))
		self.endInsertRows()
	
	def forgetStrips(self, pred):
		self.beginResetModel()
		pop_all(self.discarded_strips, lambda elt: pred(elt[0]))
		self.endResetModel()

	def remove(self, strip):
		self.forgetStrips(lambda s: s is strip)




class ShelfFilterModel(QSortFilterProxyModel):
	def __init__(self, parent, source, shelf):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(source)
		self.is_shelf = shelf
	
	def stripAt(self, index):
		return self.sourceModel().getStrip(self.mapToSource(index).row())
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		return bool(self.sourceModel().getStrip(sourceRow).lookup(shelved_detail)) == self.is_shelf
	
	def forgetStrips(self):
		self.sourceModel().forgetStrips(lambda strip: bool(strip.lookup(shelved_detail)) == self.is_shelf)


