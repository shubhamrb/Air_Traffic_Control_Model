from PyQt5.QtWidgets import QTableView
from PyQt5.QtCore import Qt

from session.config import settings
from session.env import env
from data.fpl import FPL
from gui.misc import signals, selection


# ---------- Constants ----------

# -------------------------------



class FlightPlanTableView(QTableView):
	def __init__(self, parent=None):
		QTableView.__init__(self, parent)
		signals.selectionChanged.connect(self.updateSelection)
		self.doubleClicked.connect(self.editSelectedFPL)
	
	def updateSelection(self):
		if selection.fpl == None:
			self.clearSelection()
		else:
			try:
				src_index = env.FPLs.findFPL(lambda fpl: fpl is selection.fpl)[1]
				self.selectRow(self.model().mapFromSource(self.model().sourceModel().index(src_index, 0)).row())
			except StopIteration:
				self.clearSelection()
	
	def mousePressEvent(self, event):
		QTableView.mousePressEvent(self, event)
		try:
			proxy_index = self.selectedIndexes()[0]
		except IndexError:
			return
		fpl = env.FPLs.FPL(self.model().mapToSource(proxy_index).row())
		if event.button() == Qt.MiddleButton:
			if event.modifiers() & Qt.ShiftModifier: # Trying to unlink
				if selection.strip != None and selection.strip.linkedFPL() is fpl:
					selection.strip.linkFPL(None)
					selection.selectStrip(selection.strip)
				else:
					signals.selectionChanged.emit() # revert selection
			else: # Trying to link
				if selection.strip != None and selection.strip.linkedFPL() == None and env.linkedStrip(fpl) == None:
					selection.strip.linkFPL(fpl)
					selection.selectFPL(fpl)
				else:
					signals.selectionChanged.emit() # revert selection
		else:
			selection.selectFPL(fpl)
	
	def editSelectedFPL(self):
		signals.FPLeditRequest.emit(selection.fpl)
		


