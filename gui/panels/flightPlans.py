
from datetime import timedelta

from PyQt5.QtWidgets import QWidget, QMenu, QAction, QActionGroup
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSortFilterProxyModel
from ui.fplPane import Ui_FplPanel

from session.config import settings
from session.env import env

from data.util import some
from data.fpl import FPL
from data.nav import world_navpoint_db, NavpointError

from gui.misc import signals, selection, IconFile
from gui.dialog.detailSheets import FPLdetailSheetDialog


# ---------- Constants ----------

# -------------------------------




def AD_on_map(icao):
	try:
		return env.pointOnMap(world_navpoint_db.findAirfield(icao).coordinates)
	except NavpointError:
		return False



acceptAll = lambda x: True


def ckArrDepAltAD(fpl, f):
	return fpl[FPL.ICAO_DEP] != None and f(fpl[FPL.ICAO_DEP]) \
		or fpl[FPL.ICAO_ARR] != None and f(fpl[FPL.ICAO_ARR]) or fpl[FPL.ICAO_ALT] != None and f(fpl[FPL.ICAO_ALT])




class FplFilterModel(QSortFilterProxyModel):
	include_missing_dates = True # STATIC
	
	def __init__(self, base_model, parent=None):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(base_model)
		self.callsign_filter = acceptAll
		self.arrDep_filter= acceptAll
		self.date_filter = acceptAll

	def filterAcceptsRow(self, sourceRow, sourceParent):
		fpl = self.sourceModel().FPL_list[sourceRow]
		return self.callsign_filter(fpl) and self.arrDep_filter(fpl) and \
			(FplFilterModel.include_missing_dates if fpl[FPL.TIME_OF_DEP] == None else self.date_filter(fpl))

	def setFilters(self, callsign=None, arrDep=None, date=None):
		if callsign != None:
			self.callsign_filter = callsign
		if arrDep != None:
			self.arrDep_filter = arrDep
		if date != None:
			self.date_filter = date
		self.invalidateFilter()
	
	def filter_callsign(self, fstring):
		lower = fstring.lower()
		self.setFilters(callsign=(lambda fpl: lower in some(fpl[FPL.CALLSIGN], '').lower()))
	
	def filter_date_today(self):
		self.setFilters(date=(lambda fpl: fpl.flightIsInTimeWindow(timedelta(hours=12))))
	
	def filter_date_week(self):
		self.setFilters(date=(lambda fpl: fpl.flightIsInTimeWindow(timedelta(days=3, hours=12))))
	
	def filter_arrDep_all(self):
		self.setFilters(arrDep=acceptAll)
	
	def filter_arrDep_inRange(self):
		self.setFilters(arrDep=(lambda fpl: ckArrDepAltAD(fpl, AD_on_map)))
	
	def filter_arrDep_here(self):
		here = settings.location_code
		self.setFilters(arrDep=(lambda fpl: ckArrDepAltAD(fpl, (lambda ad: ad != None and ad.upper() == here))))




# ================================================ #

#                     WIDGETS                      #

# ================================================ #

class FlightPlansPanel(QWidget, Ui_FplPanel):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.newFPL_button.setIcon(QIcon(IconFile.action_newFPL))
		self.remove_button.setIcon(QIcon(IconFile.button_bin))
		self.list_model = FplFilterModel(env.FPLs, self)
		self.list_view.setModel(self.list_model)
		self.list_view.horizontalHeader().resizeSection(0, 40)
		self.filterCallsign_edit.setClearButtonEnabled(True)
		self._create_filter_menus()
		self.updateButtons()
		self.filterCallsign_edit.textChanged.connect(self.list_model.filter_callsign)
		self.checkNow_button.clicked.connect(signals.fplUpdateRequest.emit)
		self.newFPL_button.clicked.connect(lambda: self.createLocalFPL(link=None))
		self.revert_button.clicked.connect(self.revertLocalChanges)
		self.remove_button.clicked.connect(self.removeFPL)
		signals.selectionChanged.connect(self.updateButtons)
		signals.FPLeditRequest.connect(self.editFPL)
		signals.newLinkedFPLrequest.connect(lambda s: self.createLocalFPL(link=s))
		
	def _create_filter_menus(self):
		# Airport filters
		arrDep_action_group = QActionGroup(self)
		self._add_filter_action(arrDep_action_group, 'All', self.list_model.filter_arrDep_all, ticked=True)
		self._add_filter_action(arrDep_action_group, 'On map', self.list_model.filter_arrDep_inRange)
		if env.airport_data != None:
			self._add_filter_action(arrDep_action_group, 'Here only', self.list_model.filter_arrDep_here)
		arrDep_filter_menu = QMenu()
		arrDep_filter_menu.addActions(arrDep_action_group.actions())
		self.filterArrDep_button.setMenu(arrDep_filter_menu)
		# Date filters
		date_action_group = QActionGroup(self)
		self._add_filter_action(date_action_group, '+/- 3 days', self.list_model.filter_date_week)
		self._add_filter_action(date_action_group, 'Today (~24 h)', self.list_model.filter_date_today, ticked=True)
		date_filter_menu = QMenu()
		date_filter_menu.addActions(date_action_group.actions())
		self.filterDate_button.setMenu(date_filter_menu)
		
	def _add_filter_action(self, group, text, f, ticked=False):
		action = QAction(text, self)
		action.setCheckable(True)
		action.setChecked(ticked)
		action.triggered.connect(f)
		if ticked:
			f()
		group.addAction(action)
	
	def updateButtons(self):
		fpl = selection.fpl
		self.revert_button.setEnabled(fpl != None and fpl.existsOnline() and fpl.needsUpload())
		self.remove_button.setEnabled(fpl != None and not fpl.existsOnline() and env.linkedStrip(fpl) == None)
	
	def createLocalFPL(self, link=None):
		'''
		Optional strip to link to after FPL is created. If given, it must already be in the live strips model.
		'''
		new_fpl = FPL()
		if link != None:
			for d in FPL.details:
				new_fpl[d] = link.lookup(d, fpl=False)
		dialog = FPLdetailSheetDialog(self, new_fpl)
		dialog.exec()
		if dialog.result() > 0: # not rejected
			env.FPLs.addFPL(new_fpl)
			if link != None:
				link.linkFPL(new_fpl, autoFillOK=False)
			selection.selectFPL(new_fpl)
	
	def editFPL(self, fpl):
		FPLdetailSheetDialog(self, fpl).exec()
		self.updateButtons()
	
	def revertLocalChanges(self):
		if selection.fpl != None:
			selection.fpl.revertToOnlineValues()
			env.FPLs.refreshViews()
	
	def removeFPL(self):
		env.FPLs.removeFPL(selection.fpl)
		selection.deselect()
		self.updateButtons()
		
