from PyQt5.QtWidgets import QWidget, QGraphicsView, QInputDialog, QMessageBox
from PyQt5.QtGui import QTransform, QIcon
from PyQt5.QtCore import pyqtSignal

from ui.routeEditWidget import Ui_routeEditWidget

from session.config import settings
from ext.resources import route_presets_file

from data.util import some
from data.utc import datestr, timestr
from data.nav import world_navpoint_db, world_routing_db, NavpointError

from gui.misc import signals, IconFile
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

zoom_factor = 1.25
manual_entry_exit_point_max_dist = 100 # NM

# -------------------------------





class RouteView(QGraphicsView):	
	def __init__(self, parent):
		QGraphicsView.__init__(self, parent)
		self.scale = .25
		self.setTransform(QTransform.fromScale(self.scale, self.scale))
		
	def wheelEvent(self, event):
		if event.angleDelta().y() > 0:
			self.scale *= zoom_factor
		else:
			self.scale /= zoom_factor
		self.setTransform(QTransform.fromScale(self.scale, self.scale))




def input_entry_exit_point(parent_widget, is_exit, ad):
	'''
	returns None if cancelled
	'''
	res = None
	eestr = ['entry', 'exit'][is_exit]
	while res == None:
		txt, ok = QInputDialog.getText(parent_widget, 'Missing %s point' % eestr, \
			'No %s points specified for %s (see "resources/nav/Notice" for more details).\nManual entry:' % (eestr, ad.code))
		if not ok:
			return None
		try:
			p = world_navpoint_db.findClosest(ad.coordinates, code=txt)
			if p.coordinates.distanceTo(ad.coordinates) <= manual_entry_exit_point_max_dist:
				res = p
			else:
				raise NavpointError()
		except NavpointError:
			QMessageBox.critical(parent_widget, 'Entry/exit point error', 'No such navpoint in the vicinity of %s' % ad.code)
	return res





class RouteEditWidget(QWidget, Ui_routeEditWidget):
	viewRoute_signal = pyqtSignal()
	
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.view_button.setIcon(QIcon(IconFile.button_view))
		self.clear_button.setIcon(QIcon(IconFile.button_clear))
		self.saveAsPreset_button.setIcon(QIcon(IconFile.button_save))
		self.setFocusProxy(self.route_edit)
		self.data_DEP = None # Airfield
		self.data_ARR = None # Airfield
		self._updateButtons()
		self.route_edit.textChanged.connect(self._updateButtons)
		self.suggest_button.clicked.connect(self.suggestRoute)
		self.recall_button.clicked.connect(self.recallPreset)
		self.view_button.clicked.connect(self.viewRoute_signal.emit)
		self.saveAsPreset_button.clicked.connect(self.savePreset)
		self.clear_button.clicked.connect(self.clearRoute)
	
	def _updateButtons(self):
		if self.data_DEP == None or self.data_ARR == None:
			for button in self.view_button, self.suggest_button, self.recall_button, self.saveAsPreset_button:
				button.setEnabled(False)
		else:
			self.view_button.setEnabled(True)
			self.suggest_button.setEnabled(self.data_DEP.code != self.data_ARR.code)
			self.recall_button.setEnabled((self.data_DEP.code, self.data_ARR.code) in settings.route_presets)
			self.saveAsPreset_button.setEnabled(self.getRouteText() != '')
		self.clear_button.setEnabled(self.getRouteText() != '')
	
	def setDEP(self, airport):
		self.data_DEP = airport
		self._updateButtons()
	
	def setARR(self, airport):
		self.data_ARR = airport
		self._updateButtons()
	
	def resetDEP(self):
		self.data_DEP = None
		self._updateButtons()
	
	def resetARR(self):
		self.data_ARR = None
		self._updateButtons()
	
	def setRouteText(self, txt):
		self.route_edit.setPlainText(txt)
	
	def getRouteText(self):
		return self.route_edit.toPlainText()
	
	def suggestRoute(self):
		p1 = p2 = None
		if len(world_routing_db.exitsFrom(self.data_DEP)) == 0:
			p1 = input_entry_exit_point(self, True, self.data_DEP)
			if p1 == None: # cancelled
				return
		if len(world_routing_db.entriesTo(self.data_ARR)) == 0:
			p2 = input_entry_exit_point(self, False, self.data_ARR) # may be None
			if p2 == None: # cancelled
				return
		try:
			sugg_route_str = world_routing_db.shortestRouteStr(some(p1, self.data_DEP), some(p2, self.data_ARR))
			if p1 != None:
				sugg_route_str = p1.code + ' ' + sugg_route_str
			if p2 != None:
				sugg_route_str += ' ' + p2.code
			if self.getRouteText() == '' or yesNo_question(self, 'Route suggestion', sugg_route_str, 'Accept suggestion above?'):
				self.setRouteText(sugg_route_str)
		except ValueError:
			QMessageBox.critical(self, 'Route suggestion', 'No route found.')
	
	def recallPreset(self):
		suggestions = settings.route_presets[self.data_DEP.code, self.data_ARR.code]
		if self.getRouteText() == '' and len(suggestions) == 1:
			self.setRouteText(suggestions[0])
		else:
			text, ok = QInputDialog.getItem(self, 'Route suggestions', \
				'From %s to %s:' % (self.data_DEP, self.data_ARR), suggestions, editable=False)
			if ok:
				self.setRouteText(text)
		self.route_edit.setFocus()
	
	def savePreset(self):
		icao_pair = self.data_DEP.code, self.data_ARR.code
		route_txt = ' '.join(self.getRouteText().split())
		got_routes = settings.route_presets.get(icao_pair, [])
		if route_txt == '' or route_txt in got_routes:
			QMessageBox.critical(self, 'Route preset rejected', 'This route entry is already saved!')
			return
		msg = 'Saving a route preset between %s and %s.' % icao_pair
		if got_routes != []:
			msg += '\n(%d route%s already saved for these end airports)' % (len(got_routes), ('s' if len(got_routes) != 1 else ''))
		if yesNo_question(self, 'Saving route preset', msg, 'Confirm?'):
			try:
				settings.route_presets[icao_pair].append(route_txt)
			except KeyError:
				settings.route_presets[icao_pair] = [route_txt]
			self.recall_button.setEnabled(True)
			try:
				with open(route_presets_file, mode='a', encoding='utf8') as f:
					f.write('\n# Saved on %s at %s UTC:\n' % (datestr(), timestr()))
					f.write('%s %s\t%s\n\n' % (self.data_DEP.code, self.data_ARR.code, route_txt))
				QMessageBox.information(self, 'Route preset saved', 'Check file %s to remove or edit.' % route_presets_file)
			except OSError:
				QMessageBox.critical(self, 'Error', 'There was an error writing to "%s".\nYour preset will be lost at the end of the session.')
	
	def clearRoute(self):
		self.route_edit.setPlainText('') # "clear" would remove undo/redo history
		self.route_edit.setFocus()

