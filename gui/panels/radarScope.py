from math import log, exp

from PyQt5.QtWidgets import QWidget, QGraphicsView, QMenu, QAction, QActionGroup, QMessageBox
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from ui.radarScope import Ui_radarScopeFrame

from session.config import settings
from session.env import env

from data.nav import Navpoint, NavpointError
from data.strip import parsed_route_detail
from data.instruction import Instruction

from ext.xplane import get_airport_data
from ext.resources import navpointFromSpec, read_point_spec

from gui.misc import signals, selection, IconFile
from gui.widgets.miscWidgets import AirportListSearchDialog
from gui.graphics.radarScene import Layer, RadarScene
from gui.graphics.miscGraphics import BgPixmapItem
from gui.dialog.bgImg import PositionBgImgDialog
from gui.dialog.miscDialogs import yesNo_question, RouteSpecsLostDialog


# ---------- Constants ----------

max_zoom_factor = 1000
max_zoom_range = .1 # NM
auto_bgimg_spec_file_prefix = 'auto-'

# -------------------------------



class ScopeFrame(QWidget, Ui_radarScopeFrame):
	windowClosing = pyqtSignal() # workspace-level signal
	
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.lockPanZoom_button.setIcon(QIcon(IconFile.button_lockRadar))
		self.mouse_info.clear()
		self.scene = RadarScene(self)
		self.scopeView.setScene(self.scene)
		self.courseLineFlyTime_edit.setValue(self.scene.speedMarkCount())
		self.last_airfield_clicked = None
		self.LDG_disp_actions = {}
		# BG IMAGES menu
		self.rebuildImgToggleMenu()
		# Nav menu
		nav_menu = QMenu()
		self._addMenuToggleAction(nav_menu, 'Navaids', True, self.scene.layers[Layer.NAV_AIDS].setVisible)
		self._addMenuToggleAction(nav_menu, 'Fixes', False, self.scene.layers[Layer.NAV_FIXES].setVisible)
		self._addMenuToggleAction(nav_menu, 'RNAV points', False, self.scene.layers[Layer.RNAV_POINTS].setVisible)
		nav_menu.addSeparator()
		self._addMenuToggleAction(nav_menu, 'Airfields', False, self.scene.layers[Layer.NAV_AIRFIELDS].setVisible)
		self.nav_menuButton.setMenu(nav_menu)
		# AD menu
		AD_menu = QMenu()
		self._addMenuToggleAction(AD_menu, 'Ground routes', False, self.scene.showGroundNetworks)
		self._addMenuToggleAction(AD_menu, 'Taxiway names', False, self.scene.showTaxiwayNames)
		self._addMenuToggleAction(AD_menu, 'Highlight TWYs under mouse', True, self.scene.highlightEdgesOnMouseover)
		self._addMenuToggleAction(AD_menu, 'RWY names always visible', False, self.scene.setRunwayNamesAlwaysVisible)
		AD_menu.addSeparator()
		self._addMenuToggleAction(AD_menu, 'Parking positions', True, self.scene.layers[Layer.PARKING_POSITIONS].setVisible)
		self._addMenuToggleAction(AD_menu, 'Holding lines', False, self.scene.layers[Layer.HOLDING_LINES].setVisible)
		self._addMenuToggleAction(AD_menu, 'Taxiway centre lines', False, self.scene.layers[Layer.TAXIWAY_LINES].setVisible)
		self._addMenuToggleAction(AD_menu, 'Other objects', True, self.scene.layers[Layer.AIRPORT_OBJECTS].setVisible)
		self.AD_menuButton.setMenu(AD_menu)
		# LDG menu
		if env.airport_data == None:
			self.LDG_menuButton.setEnabled(False)
		else:
			LDG_menu = QMenu()
			self.syncLDG_action = self._addMenuToggleAction(LDG_menu, 'Sync with arrival runway selection', True, self.setSyncLDG)
			for rwy in env.airport_data.allRunways(sortByName=True): # all menu options set to False below; normally OK at start
				txt = 'RWY %s' % rwy.name
				if rwy.ILS_cat != None:
					txt += ' (%s)' % rwy.ILS_cat
				action = self._addMenuToggleAction(LDG_menu, txt, False, lambda b, r=rwy.name: self.scene.showLandingHelper(r, b))
				action.triggered.connect(lambda b: self.syncLDG_action.setChecked(False)) # cancel sync when one is set manually (triggered)
				self.LDG_disp_actions[rwy.name] = action
			LDG_menu.addSeparator()
			self._addMenuToggleAction(LDG_menu, 'Slope altitudes', True, self.scene.showSlopeAltitudes)
			self._addMenuToggleAction(LDG_menu, 'LOC interception cones', False, self.scene.showInterceptionCones)
			self.LDG_menuButton.setMenu(LDG_menu)
		# ACFT menu
		ACFT_menu = QMenu()
		self._addMenuToggleAction(ACFT_menu, 'Filter out unlinked GND modes', False, lambda b: self.scene.showGndModes(not b))
		ACFT_menu.addSeparator()
		self._addMenuToggleAction(ACFT_menu, 'Selected ACFT course/assignments', True, self.scene.showSelectionAssignments)
		self._addMenuToggleAction(ACFT_menu, 'All courses/vectors', False, self.scene.showVectors)
		self._addMenuToggleAction(ACFT_menu, 'All routes', False, self.scene.showRoutes)
		ACFT_menu.addSeparator()
		self._addMenuToggleAction(ACFT_menu, 'Unlinked radar tags', True, self.scene.showUnlinkedTags)
		self._addMenuToggleAction(ACFT_menu, 'Separation rings', False, self.scene.showSeparationRings)
		self.ACFT_menuButton.setMenu(ACFT_menu)
		# OPTIONS menu
		options_menu = QMenu()
		self.autoCentre_action = self._addMenuToggleAction(options_menu, 'Centre on indications', False, None)
		self._addMenuToggleAction(options_menu, 'Show custom labels', True, self.scene.layers[Layer.CUSTOM_LABELS].setVisible)
		self.showRdfLine_action = self._addMenuToggleAction(options_menu, 'Show RDF line', False, self.scene.showRdfLine)
		options_menu.addSeparator()
		drawAirport_action = QAction('Draw additional airport...', self)
		drawAirport_action.triggered.connect(self.drawAdditionalAirport)
		resetAirports_action = QAction('Reset drawn airports', self)
		resetAirports_action.triggered.connect(self.scene.resetAirportItems)
		options_menu.addAction(drawAirport_action)
		options_menu.addAction(resetAirports_action)
		self.options_menuButton.setMenu(options_menu)
		# Other actions and signals
		self.lockPanZoom_button.toggled.connect(self.lockRadar)
		self.courseLineFlyTime_edit.valueChanged.connect(self.scene.setSpeedMarkCount)
		self.scene.mouseInfo.connect(self.mouse_info.setText)
		self.scene.addRemoveRouteNavpoint.connect(self.addRemoveRouteNavpointToSelection)
		self.scene.imagesRedrawn.connect(self.rebuildImgToggleMenu)
		self.zoomLevel_slider.valueChanged.connect(self.changeZoomLevel)
		self.scopeView.zoom_signal.connect(self.zoom)
		# External signal connections below. CAUTION: these must all be disconnected on widget deletion
		signals.selectionChanged.connect(self.mouse_info.clear)
		signals.runwayUseChanged.connect(self.updateLdgMenuAndDisplay)
		signals.localSettingsChanged.connect(self.updateRdfMenuAction)
		signals.navpointClick.connect(self.setLastAirfieldClicked)
		signals.indicatePoint.connect(self.indicatePoint)
		signals.mainWindowClosing.connect(self.close)
		# Finish up
		self.sync_LDG_display = True
		self.updateLdgMenuAndDisplay()
		self.updateRdfMenuAction()
		self.scopeView.moveToShow(env.radarPos())
		self.f_scale = lambda x: max_zoom_factor / exp(x * log(settings.map_range / max_zoom_range)) # x in [0, 1]
		self.changeZoomLevel(self.zoomLevel_slider.value())
	
	def _addMenuToggleAction(self, menu, text, init_state, toggle_function):
		action = QAction(text, self)
		action.setCheckable(True)
		menu.addAction(action)
		action.setChecked(init_state)
		if toggle_function != None:
			toggle_function(init_state)
			action.toggled.connect(toggle_function)
		return action
	
	def indicatePoint(self, coords):
		if env.pointOnMap(coords):
			if not self.lockPanZoom_button.isChecked() and self.autoCentre_action.isChecked():
				self.scopeView.moveToShow(coords)
			self.scene.point_indicator.indicate(coords)
		else: # point is off map
			hdg = env.radarPos().headingTo(coords)
			signals.statusBarMsg.emit('Point is off map to the %s' % hdg.approxCardinal(True))
	
	
	## GUI UPDATES
	
	def rebuildImgToggleMenu(self):
		img_list = self.scene.layerItems(Layer.BG_IMAGES)
		img_menu = QMenu()
		for img_item in img_list:
			self._addMenuToggleAction(img_menu, img_item.title, False, img_item.setVisible)
		self.bgImg_menuButton.setMenu(img_menu)
		self.bgImg_menuButton.setEnabled(img_list != [])
	
	def setLastAirfieldClicked(self, navpoint):
		if navpoint.type == Navpoint.AD:
			self.last_airfield_clicked = navpoint
	
	def updateRdfMenuAction(self):
		self.showRdfLine_action.setEnabled(settings.radio_direction_finding)
	
	def updateLdgMenuAndDisplay(self):
		if self.sync_LDG_display and env.airport_data != None:
			for rwy, action in self.LDG_disp_actions.items():
				action.setChecked(env.airport_data.runway(rwy).use_for_arrivals)
	
	def changeZoomLevel(self, percent_level):
		'''
		percent_level is a value in [0, 100]
		'''
		self.scopeView.setScaleFactor(self.f_scale(1 - percent_level / 100))
	
	
	## ACTIONS
	
	def setSyncLDG(self, toggle):
		self.sync_LDG_display = toggle
		if toggle:
			self.updateLdgMenuAndDisplay()
	
	def drawAdditionalAirport(self):
			init = '' if self.last_airfield_clicked == None else self.last_airfield_clicked.code
			dialog = AirportListSearchDialog(self, env.navpoints, initCodeFilter=init)
			dialog.exec()
			if dialog.result() > 0 and yesNo_question(self, 'Draw additional airport', \
					'CAUTION: This may freeze the program for a few seconds.', 'OK?'):
				ad = dialog.selectedAirport()
				try:
					ad_data = get_airport_data(ad.code)
					self.scene.drawAdditionalAirportData(ad_data)
					signals.indicatePoint.emit(ad_data.navpoint.coordinates)
					self.last_airfield_clicked = None
				except NavpointError:
					print('ERROR: No airport "%s" to draw in map range. Please report with details.' % ad)
	
	def zoom(self, zoom_in):
		step = self.zoomLevel_slider.pageStep()
		if not zoom_in: # zooming OUT
			step = -step
		self.zoomLevel_slider.setValue(self.zoomLevel_slider.value() + step)
	
	def lockRadar(self, lock):
		scroll = Qt.ScrollBarAlwaysOff if lock else Qt.ScrollBarAsNeeded
		self.scopeView.setVerticalScrollBarPolicy(scroll)
		self.scopeView.setHorizontalScrollBarPolicy(scroll)
		self.zoomLevel_slider.setVisible(not lock)
		self.autoCentre_action.setEnabled(not lock)
		self.scene.lockMousePanAndZoom(lock)
	
	def positionVisibleBgImages(self):
		imglst_all = self.scene.layerItems(Layer.BG_IMAGES)
		imglst_moving = [item for item in imglst_all if item.isVisible() and isinstance(item, BgPixmapItem)]
		PositionBgImgDialog(imglst_moving, self).exec()
		file_name = settings.outputFileName(auto_bgimg_spec_file_prefix + settings.location_code, ext='lst', sessionID=False)
		with open(file_name, 'w', encoding='utf8') as f:
			for item in imglst_all:
				f.write(item.specLine() + '\n')
			for src, img, scale, title in settings.loose_strip_bay_backgrounds:
				f.write('%s\tLOOSE %g\t%s\n' % (src, scale, title))
		if imglst_moving != []:
			QMessageBox.information(self, 'Image positioning', 'Your changes have so far only affected the radar screen '
				'in the main window. If you like it the way it is, make sure you modify your .lst file and reload your images.\n\n'
				'File %s was also generated with your new corner coordinates for you to copy.' % file_name)
	
	def addRemoveRouteNavpointToSelection(self, navpoint):
		strip = selection.strip
		if strip == None:
			QMessageBox.critical(self, 'Add/remove point to route', 'No strip in current selection.')
			return
		route = strip.lookup(parsed_route_detail)
		if route == None:
			QMessageBox.critical(self, 'Add/remove point to route', 'Departure or arrival airport not recognised on strip.')
			return
		dialog = None
		if navpoint in route: # Remove navpoint from route
			lost_before, lost_after = strip.removeRouteWaypoint(navpoint)
			if lost_before != [] or lost_after != []:
				dialog = RouteSpecsLostDialog(self, 'Waypoint %s removed' % navpoint, \
						'%s [%s] %s' % (' '.join(lost_before), navpoint, ' '.join(lost_after)))
		else: # Add navpoint to route
			lost_specs = strip.insertRouteWaypoint(navpoint)
			if lost_specs != []:
				dialog = RouteSpecsLostDialog(self, 'Waypoint %s inserted' % navpoint, ' '.join(lost_specs))
		if dialog != None:
			dialog.exec()
			if dialog.mustOpenStripDetails():
				signals.stripEditRequest.emit(strip)
		signals.stripInfoChanged.emit()
	
	
	## SAVED STATES
	
	def stateSave(self):
		if self.lockPanZoom_button.isChecked():
			xy = self.scopeView.mapToScene(self.scopeView.viewport().rect().center())
			res = {
				'lock': '1',
				'zoom': str(self.zoomLevel_slider.value()),
				'centre_x': str(xy.x()),
				'centre_y': str(xy.y())
			}
		else:
			res = {'lock': '0'}
		res['cvline_fly_time'] = str(self.courseLineFlyTime_edit.value())
		res['draw_ad'] = self.scene.drawnAirports()
		res['pin_navpoint'] = ['%s~%s' % (p, p.coordinates.toString()) for p in self.scene.pinnedNavpoints()]
		res['pin_pkg'] = ['%s %s' % (ad, pos) for ad, pos in self.scene.pinnedParkingPositions()]
		res['label'] = ['%s %s' % (pos.toString(), lbl) for pos, lbl in self.scene.customLabels()]
		for menu_button, menu_attr in (self.bgImg_menuButton, 'bg_menu'), (self.nav_menuButton, 'nav_menu'), \
				(self.AD_menuButton, 'ad_menu'), (self.LDG_menuButton, 'ldg_menu'), \
				(self.ACFT_menuButton, 'acft_menu'), (self.options_menuButton, 'opts_menu'):
			menu = menu_button.menu()
			if menu != None:
				menu_state = 0
				for i, action in enumerate(menu.actions()):
					menu_state |= int(action.isChecked()) << i
				res[menu_attr] = str(menu_state)
		return res
	
	def restoreState(self, saved_state):
		# lock/pan/zoom
		try:
			radar_locked = bool(int(saved_state['lock']))
			self.lockPanZoom_button.setChecked(radar_locked)
			if radar_locked:
				self.zoomLevel_slider.setValue(int(saved_state['zoom']))
				self.scopeView.centerOn(float(saved_state['centre_x']), float(saved_state['centre_y']))
		except (KeyError, ValueError):
			pass
		# menu options
		for menu_button, menu_attr in (self.bgImg_menuButton, 'bg_menu'), (self.nav_menuButton, 'nav_menu'), \
				(self.AD_menuButton, 'ad_menu'), (self.LDG_menuButton, 'ldg_menu'), \
				(self.ACFT_menuButton, 'acft_menu'), (self.options_menuButton, 'opts_menu'):
			menu = menu_button.menu()
			if menu != None:
				try:
					menu_state = int(saved_state[menu_attr])
					for i, action in enumerate(menu.actions()):
						if action.isCheckable() and action.isChecked() != bool(1 << i & menu_state):
							action.toggle()
				except KeyError:
					pass
		if self.sync_LDG_display:
			self.updateLdgMenuAndDisplay()
		# course/vector line fly time
		try:
			self.courseLineFlyTime_edit.setValue(int(saved_state['cvline_fly_time']))
		except (KeyError, ValueError):
			pass
		# additional ADs
		for ad in saved_state.get('draw_ad', []):
			self.scene.drawAdditionalAirportData(get_airport_data(ad)) # STYLE check if data exists?
		# pinned points
		for spec in saved_state.get('pin_navpoint', []): # str specs
			try:
				self.scene.pinNavpoint(navpointFromSpec(spec, env.navpoints))
			except NavpointError:
				print('Cannot identify navpoint to pin: %s' % spec)
		for spec in saved_state.get('pin_pkg', []): # ad+pkg specs
			split = spec.split(maxsplit=1)
			if len(split) == 2:
				self.scene.pinPkgPos(*split)
			else:
				print('Cannot identify parking position to pin: %s' % spec)
		# custom labels
		for spec in saved_state.get('label', []): # ad+pkg specs
			split = spec.split(maxsplit=1)
			if len(split) == 2:
				try:
					self.scene.addCustomLabel(split[1], read_point_spec(split[0], env.navpoints).toQPointF())
				except ValueError:
					print('Cannot restore label: bad position string "%s"' % split[0])
			else:
				print('Cannot restore label (missing text or position): %s' % spec)
	
	
	## CLOSING

	def closeEvent(self, event):
		self.scene.disconnectAllSignals()
		signals.selectionChanged.disconnect(self.mouse_info.clear)
		signals.runwayUseChanged.disconnect(self.updateLdgMenuAndDisplay)
		signals.localSettingsChanged.disconnect(self.updateRdfMenuAction)
		signals.navpointClick.disconnect(self.setLastAirfieldClicked)
		signals.indicatePoint.disconnect(self.indicatePoint)
		signals.mainWindowClosing.disconnect(self.close)
		event.accept()
		self.windowClosing.emit()
		QWidget.closeEvent(self, event)

