from PyQt5.QtWidgets import QTableView
from PyQt5.QtCore import Qt

from session.env import env
from gui.misc import signals


# ---------- Constants ----------

# -------------------------------



class AtcTableView(QTableView):
	def __init__(self, parent=None):
		QTableView.__init__(self, parent)
	
	def mouseDoubleClickEvent(self, event):
		index = self.indexAt(event.pos())
		if index.isValid() and event.button() == Qt.LeftButton:
			atc = env.ATCs.atcOnRow(index.row()).callsign
			if event.modifiers() & Qt.ShiftModifier:
				try:
					pos = env.ATCs.getATC(atc).position
					if pos == None:
						signals.statusBarMsg.emit('Position unknown for %s' % atc)
					else:
						signals.indicatePoint.emit(pos)
				except KeyError:
					pass
			else: # double-click, no SHIFT
				signals.privateAtcChatRequest.emit(atc)
			event.accept()
		else:
			QTableView.mouseDoubleClickEvent(self, event)


