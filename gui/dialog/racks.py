from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex

from ui.rackVisibilityDialog import Ui_rackVisibilityDialog

from session.env import env
from session.config import settings

from gui.widgets.miscWidgets import RadioKeyEventFilter
from gui.graphics.miscGraphics import coloured_square_icon


# ---------- Constants ----------

# -------------------------------



class RackVisibilityDialog(QDialog, Ui_rackVisibilityDialog):
	def __init__(self, visible_racks, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.table_model = RackVisibilityTableModel(self, visible_racks)
		self.tableView.setModel(self.table_model)
		self.selectAll_button.clicked.connect(lambda: self.table_model.globalSelect(True))
		self.selectNone_button.clicked.connect(lambda: self.table_model.globalSelect(False))
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
	
	def getSelection(self):
		return self.table_model.getSelectedRacks()
		




class RackVisibilityTableModel(QAbstractTableModel):
	def __init__(self, parent, racks):
		QAbstractTableModel.__init__(self, parent)
		self.racks = racks
		self.ticked = len(racks) * [False]
	
	def getSelectedRacks(self):
		return [r for r, v in zip(self.racks, self.ticked) if v]
	
	def globalSelect(self, b):
		self.ticked = len(self.racks) * [b]
		self.dataChanged.emit(self.index(0, 0), self.index(0, len(self.racks)))
	
	# MODEL STUFF
	def rowCount(self, parent=QModelIndex()):
		return len(self.racks)

	def columnCount(self, parent=QModelIndex()):
		return 1
	
	def flags(self, index):
		return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			return None

	def data(self, index, role):
		if index.column() == 0:
			row = index.row()
			if role == Qt.DisplayRole:
				return self.racks[row]
			elif role == Qt.CheckStateRole:
				return Qt.Checked if self.ticked[row] else Qt.Unchecked
			elif role == Qt.DecorationRole:
				if self.racks[row] in settings.rack_colours:
					return coloured_square_icon(settings.rack_colours[self.racks[row]], width=24)
	
	def setData(self, index, value, role):
		if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
			row = index.row()
			self.ticked[row] = value == Qt.Checked
			return True
		return False

