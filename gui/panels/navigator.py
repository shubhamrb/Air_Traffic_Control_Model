
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget

from ui.navigator import Ui_navigator
from ui.airportSearchWidget import Ui_airportSearchWidget

from session.env import env
from data.nav import Airfield
from gui.misc import signals
from models.navpoints import MapNavpointFilterModel, AirportNameFilterModel


# ---------- Constants ----------

# -------------------------------


class NavigatorFrame(QWidget, Ui_navigator):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.filter_edit.setClearButtonEnabled(True)
		self.table_model = MapNavpointFilterModel(env.navpoints, parent=self)
		self.table_model.setTypeFilters(rnav=False) # assumed GUI default: all types but RNAV; incl. names and no text filter
		self.table_view.setModel(self.table_model)
		for i in range(self.table_model.columnCount()):
			self.table_view.resizeColumnToContents(i)
		self.airfieldFilter_button.toggled.connect(lambda b: self.table_model.setTypeFilters(ad=b))
		self.aidFilter_button.toggled.connect(lambda b: self.table_model.setTypeFilters(aid=b))
		self.fixFilter_button.toggled.connect(lambda b: self.table_model.setTypeFilters(fix=b))
		self.rnavFilter_button.toggled.connect(lambda b: self.table_model.setTypeFilters(rnav=b))
		self.pkgFilter_button.toggled.connect(lambda b: self.table_model.setTypeFilters(pkg=b))
		self.includeLongNamesFilter_button.toggled.connect(self.table_model.setSearchInNames)
		self.filter_edit.textChanged.connect(self.table_model.setTextFilter)
		self.table_view.doubleClicked.connect(self.indicateNavpoint)
		signals.navpointClick.connect(lambda p: self.filter_edit.setText(p.code))
		signals.pkPosClick.connect(self.filter_edit.setText)
	
	def focusInEvent(self, event):
		QWidget.focusInEvent(self, event)
		self.filter_edit.setFocus()
		self.filter_edit.selectAll()
	
	def indicateNavpoint(self, table_index):
		src_row = self.table_model.mapToSource(table_index).row()
		signals.indicatePoint.emit(self.table_model.sourceModel().coordsForRow(src_row))





##  WORLD AIRPORT SEARCH  ##


class AirportNavigatorWidget(QWidget, Ui_airportSearchWidget):
	airportDoubleClicked = pyqtSignal(Airfield)
	
	def __init__(self, parent, nav_db):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.setFocusProxy(self.filter_edit)
		self.filter_edit.setClearButtonEnabled(True)
		self.table_model = AirportNameFilterModel(nav_db, parent=self)
		self.table_view.setModel(self.table_model)
		for i in range(self.table_model.columnCount()):
			self.table_view.resizeColumnToContents(i)
		self.search_button.clicked.connect(self.updateTableContents)
		self.table_view.doubleClicked.connect(self.doubleClick)
	
	def updateTableContents(self): # from what is in the selected text field
		if self.codeFilter_radioButton.isChecked():
			self.table_model.setCodeFilter(self.filter_edit.text())
		else:
			self.table_model.setNameFilter(self.filter_edit.text())
	
	def setAndUpdateFilter(self, is_code, text):
		if is_code:
			self.codeFilter_radioButton.setChecked(True)
		else:
			self.nameFilter_radioButton.setChecked(True)
		self.filter_edit.setText(text)
		self.updateTableContents()
	
	def doubleClick(self, table_index):
		self.airportDoubleClicked.emit(self.table_model.navpointAtIndex(table_index))
	
	def selectedAirport(self):
		try:
			return self.table_model.navpointAtIndex(self.table_view.selectedIndexes()[0])
		except IndexError:
			return None


