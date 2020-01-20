
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt, QAbstractTableModel
from ui.routeDialog import Ui_routeDialog

from session.config import settings
from data.nav import Navpoint
from data.db import cruise_speed
from data.coords import dist_str
from data.params import Speed, TTF_str
from gui.misc import signals
from gui.graphics.routeScene import RouteScene
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

# -------------------------------



class RouteTableModel(QAbstractTableModel):
	# STATIC:
	column_headers = ['Leg', 'Start', 'Leg spec', 'Waypoint', 'Initial hdg', 'Distance', 'Final hdg']

	def __init__(self, route, parent):
		QAbstractTableModel.__init__(self, parent)
		self.route = route
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return RouteTableModel.column_headers[section]

	def rowCount(self, parent=None):
		return self.route.legCount()

	def columnCount(self, parent=None):
		return len(RouteTableModel.column_headers)

	def data(self, index, role):
		row = index.row()
		col = index.column()
		if role == Qt.DisplayRole:
			if col == 0:
				return str(row + 1)
			elif col == 1:
				if row == 0:
					return self.route.dep.code
				else:
					return self.route.waypoint(row - 1).code
			elif col == 2:
				return ' '.join(self.route.legSpec(row))
			elif col == 3:
				return self.route.waypoint(row).code
			else:
				wp = self.route.waypoint(row)
				prev = self.route.dep if row == 0 else self.route.waypoint(row - 1)
				if col == 4:
					return prev.coordinates.headingTo(wp.coordinates).read() + '°'
				elif col == 5:
					return dist_str(prev.coordinates.distanceTo(wp.coordinates))
				elif col == 6:
					return wp.coordinates.headingFrom(prev.coordinates).read() + '°'
				
		elif role == Qt.ToolTipRole:
			if col == 1:
				prev = self.route.dep if row == 0 else self.route.waypoint(row - 1)
				return Navpoint.tstr(prev.type)
			elif col == 3:
				wp = self.route.waypoint(row)
				return Navpoint.tstr(wp.type)
			elif col == 4 or col == 6:
				return 'True heading'





class RouteDialog(QDialog, Ui_routeDialog):
	def __init__(self, route, speedHint=None, acftHint=None, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.depICAO_info.setText(route.dep.code)
		self.depAD_info.setText(route.dep.long_name)
		self.arrICAO_info.setText(route.arr.code)
		self.arrAD_info.setText(route.arr.long_name)
		self.route_length = route.totalDistance()
		self.totalRouteDistance_info.setText(dist_str(self.route_length))
		self.route_scene = RouteScene(route, parent=self)
		self.route_view.setScene(self.route_scene)
		self.route_table.setModel(RouteTableModel(route, self))
		for col in [0, 1, 3, 4, 6]:
			self.route_table.resizeColumnToContents(col)
		speedHint_OK = speedHint != None and self.speed_edit.minimum() <= speedHint.kt <= self.speed_edit.maximum()
		if speedHint_OK:
			self.speed_edit.setValue(speedHint.kt)
		if acftHint != None:
			self.acftType_select.setEditText(acftHint)
			if not speedHint_OK:
				self.EETfromACFT_radioButton.setChecked(True)
		self.updateEET()
		self.route_table.selectionModel().selectionChanged.connect(self.legSelectionChanged)
		self.OK_button.clicked.connect(self.accept)
		self.EETfromSpeed_radioButton.toggled.connect(self.updateEET)
		self.EETfromACFT_radioButton.toggled.connect(self.updateEET)
		self.speed_edit.valueChanged.connect(self.updateEET)
		self.acftType_select.editTextChanged.connect(self.updateEET)
	
	def legSelectionChanged(self):
		self.route_scene.setSelectedLegs([index.row() for index in self.route_table.selectionModel().selectedRows()])
	
	def updateEET(self):
		if self.EETfromSpeed_radioButton.isChecked():
			self.EET_info.setText(TTF_str(self.route_length, Speed(self.speed_edit.value())))
		elif self.EETfromACFT_radioButton.isChecked():
			crspd = cruise_speed(self.acftType_select.getAircraftType())
			if crspd == None:
				self.EET_info.setText('(unknown ACFT cruise speed)')
			else:
				try:
					self.EET_info.setText(TTF_str(self.route_length, crspd))
				except ValueError:
					self.EET_info.setText('(speed too low)')

