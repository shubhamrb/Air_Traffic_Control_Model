from PyQt5.QtWidgets import QStackedWidget, QMdiArea, QMdiSubWindow, QTabWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon

from gui.misc import IconFile
from gui.panels.stripPanes import LooseStripPane, StripRacksPane
from gui.panels.radarScope import ScopeFrame
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

# -------------------------------


# === NOTE ===
# A workspace window can be any widget, provided:
# - it implements a "stateSave" and a "restoreState" method
# - it signals "windowClosing" on closing
# - before windowClosing, it disconnects all of the external signals it connected


class WorkspaceMdiArea(QMdiArea):
	def __init__(self, parent):
		QMdiArea.__init__(self, parent)
		self.setTabPosition(QTabWidget.South) # only affects tabbed view
		self.setTabsMovable(True) # only affects tabbed view
		self.setTabsClosable(True) # only affects tabbed view
		self.setDocumentMode(True) # only affects tabbed view
	
	def addWorkspaceMdiWindow(self, widget):
		window = QMdiSubWindow()
		window.setWidget(widget)
		window.setAttribute(Qt.WA_DeleteOnClose)
		window.setWindowIcon(QIcon(WorkspaceWidget.window_icons[widget._workspace_widget_type]))
		self.addSubWindow(window)
		window.show()
		widget.show()
	
	def removeWorkspaceMdiWindow(self, window):
		widget = window.widget()
		self.removeSubWindow(widget) # spec: sets window widget to 0 but window not removed
		self.removeSubWindow(window) # spec: sets window parent to 0 and removes window
		window.deleteLater()
		return widget






class WorkspaceWidget(QStackedWidget):
	# STATIC
	window_types = LOOSE_BAY, RADAR_SCREEN, STRIP_PANEL = range(3)
	window_icons = IconFile.panel_looseBay, IconFile.panel_radarScreen, IconFile.panel_racks # NB: share indexes with window_types
	
	def __init__(self, parent):
		QStackedWidget.__init__(self, parent)
		self.mdi_area = WorkspaceMdiArea(self)
		self.popped_out_widgets = {} # int assigned index -> window widget
		self.addWidget(self.mdi_area)
	
	def windowedView(self):
		return self.mdi_area.viewMode() == QMdiArea.SubWindowView
	
	def switchWindowedView(self, toggle):
		page = self.currentWidget()
		if toggle: # set to windowed view
			if page is not self.mdi_area:
				self.removeWidget(page) # spec: does not delete the widget
				self.mdi_area.addWorkspaceMdiWindow(page)
			self.mdi_area.setViewMode(QMdiArea.SubWindowView)
			self.mdi_area.setOption(QMdiArea.DontMaximizeSubWindowOnActivation, on=True)
		else: # set to tabbed view
			self.mdi_area.setOption(QMdiArea.DontMaximizeSubWindowOnActivation, on=False)
			self.mdi_area.setViewMode(QMdiArea.TabbedView)
			if page is self.mdi_area: # normally the case
				windows = self.mdi_area.subWindowList()
				if len(windows) == 1:
					widget = self.mdi_area.removeWorkspaceMdiWindow(windows[0])
					self.setCurrentIndex(self.addWidget(widget))
	
	def containedWorkspaceWidgets(self):
		page = self.currentWidget()
		return [w.widget() for w in self.mdi_area.subWindowList()] if page is self.mdi_area else [page]
	
	def poppedWorkspaceWidgets(self):
		return list(self.popped_out_widgets.values())
	
	def getCurrentRadarPanel(self):
		page = self.currentWidget()
		if page is self.mdi_area:
			window = page.currentSubWindow()
			if window:
				widget = window.widget()
				if widget._workspace_widget_type == WorkspaceWidget.RADAR_SCREEN:
					return widget
		elif page._workspace_widget_type == WorkspaceWidget.RADAR_SCREEN:
			return page
		return None
	
	
	## PREPARING/ADDING WIDGETS
	
	def addWorkspaceWidget(self, widget_type, popOut=False):
		if widget_type == WorkspaceWidget.RADAR_SCREEN:
			widget = ScopeFrame()
		elif widget_type == WorkspaceWidget.LOOSE_BAY:
			widget = LooseStripPane()
		elif widget_type == WorkspaceWidget.STRIP_PANEL:
			widget = StripRacksPane()
		else:
			raise ValueError('Bad workspace window type %d' % widget_type)
		all_widgets = self.containedWorkspaceWidgets() + self.poppedWorkspaceWidgets()
		widget_index = 0
		while any(w._workspace_widget_index == widget_index for w in all_widgets):
			widget_index += 1
		widget._workspace_widget_index = widget_index
		widget._workspace_widget_type = widget_type
		widget.windowClosing.connect(lambda i=widget_index: self.closingWindow(i))
		if popOut:
			self.openWidgetPopOut(widget)
		else:
			self.addContainedWidget(widget)
		return widget
	
	def addContainedWidget(self, widget):
		page = self.currentWidget()
		if page is not self.mdi_area: # got single contained widget stacked over MDI area
			self.removeWidget(page)
			self.mdi_area.addWorkspaceMdiWindow(page)
		if self.containedWorkspaceWidgets() == [] and not self.windowedView(): # must stack as single widget over MDI area
			self.setCurrentIndex(self.addWidget(widget))
			widget.setWindowFlags(Qt.Widget)
			widget.show()
		else:
			self.mdi_area.addWorkspaceMdiWindow(widget)
	
	def openWidgetPopOut(self, widget):
		widget.installEventFilter(RadioKeyEventFilter(widget))
		widget.setWindowFlags(Qt.Window)
		self.popped_out_widgets[widget._workspace_widget_index] = widget
		widget.show()
	
	
	## POP OUT AND RECLAIM
	
	def popOutCurrentWindow(self):
		page = self.currentWidget()
		if page is self.mdi_area:
			window = self.mdi_area.currentSubWindow()
			if window:
				to_pop_out = self.mdi_area.removeWorkspaceMdiWindow(window)
				if not self.windowedView():
					left = self.mdi_area.subWindowList()
					if len(left) == 1: # stack the last widget
						to_stack = self.mdi_area.removeWorkspaceMdiWindow(left[0])
						self.setCurrentIndex(self.addWidget(to_stack))
					elif len(left) > 1: # trick below because next tabbed widget was not being maximised after pop-out
						self.mdi_area.setViewMode(QMdiArea.SubWindowView)
						self.mdi_area.setViewMode(QMdiArea.TabbedView)
				self.openWidgetPopOut(to_pop_out)
		else:
			self.removeWidget(page)
			self.openWidgetPopOut(page)
	
	def reclaimPoppedOutWidgets(self):
		while len(self.popped_out_widgets) > 0:
			i, w = self.popped_out_widgets.popitem()
			w.hide()
			self.addContainedWidget(w)
	
	
	## CLOSING WIDGETS
		
	def closingWindow(self, window_index):
		try: # find the widget among the popped out windows
			self.popped_out_widgets.pop(window_index).deleteLater()
		except KeyError: # is a contained widget
			page = self.currentWidget()
			if page is not self.mdi_area and page._workspace_widget_index == window_index:
				# though this should not really happen until we can close a single stacked widget
				self.removeWidget(page)
				page.deleteLater()
			elif page is self.mdi_area and not self.windowedView(): # an MDI sub-window is closing and we may now want to stack a last one
				left = [w for w in self.mdi_area.subWindowList() if w.widget()._workspace_widget_index != window_index]
				if len(left) == 1:
					widget = self.mdi_area.removeWorkspaceMdiWindow(left[0])
					self.setCurrentIndex(self.addWidget(widget))
	
	
	## SAVE/RESTORE STATE
	
	def workspaceWindowsStateSave(self):
		return [(w._workspace_widget_type, False, w.stateSave()) for w in self.containedWorkspaceWidgets()] \
				+ [(w._workspace_widget_type, True, w.stateSave()) for w in self.poppedWorkspaceWidgets()]
	
	def restoreWorkspaceWindows(self, saved_windows):
		for window_type, window_popped, window_state in saved_windows:
			widget = self.addWorkspaceWidget(window_type, popOut=window_popped)
			widget.restoreState(window_state)





