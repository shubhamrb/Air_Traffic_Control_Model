
from PyQt5.QtCore import Qt, QStringListModel
from PyQt5.QtWidgets import QWidget, QInputDialog, QListView

from ui.atcTable import Ui_atcPane

from data.utc import timestr, datestr

from session.config import settings
from session.env import env

from gui.misc import signals, selection
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

# -------------------------------

class QStringListModel_displayOnly(QStringListModel):
	def __init__(self, parent=None):
		QStringListModel.__init__(self, parent)
	
	def flags(self, index):
		return Qt.ItemIsEnabled
	
	def addString(self, s):
		self.setStringList(self.stringList() + [s])



class WhoHasWidget(QListView):
	def __init__(self, parent=None):
		QListView.__init__(self, parent)
		self.setModel(QStringListModel_displayOnly(self))
		self.last_whohas_request = None
	
	def newRequest(self, acft_callsign):
		self.model().setStringList([])
		self.setWindowTitle('Claiming %s at %s (%s)' % (acft_callsign, timestr(seconds=True), datestr()))
		self.last_whohas_request = acft_callsign.upper()
	
	def processClaim(self, atc_callsign, acft_callsign):
		if acft_callsign.upper() == self.last_whohas_request: # CAUTION last is None until being shown once; uppercase afterwards
			self.model().addString(atc_callsign)



class HandoverPane(QWidget, Ui_atcPane):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.whoHas_window = WhoHasWidget(self)
		self.whoHas_window.setWindowFlags(Qt.Window)
		self.whoHas_window.installEventFilter(RadioKeyEventFilter(self))
		self.callsign_suggestion = ''
		self.ATC_view.setModel(env.ATCs)
		self.publicFrequency_edit.addFrequencies([(f, d) for f, d, t in env.frequencies if t != 'recorded'])
		self.whoHas_button.clicked.connect(self.whoHasRequest)
		self.publiciseFrequency_tickBox.toggled.connect(self.publiciseFrequency)
		self.publicFrequency_edit.frequencyChanged.connect(self.setPublicisedFrequency)
		signals.incomingContactClaim.connect(self.whoHas_window.processClaim)
		signals.selectionChanged.connect(self.updateSuggestionFromSelection)
		signals.sessionEnded.connect(env.ATCs.clear)
	
	def updateSuggestionFromSelection(self):
		cs = selection.selectedCallsign()
		if cs != None:
			self.callsign_suggestion = cs
	
	def publiciseFrequency(self, toggle):
		settings.publicised_frequency = self.publicFrequency_edit.getFrequency() if toggle else None
	
	def setPublicisedFrequency(self, frq):
		settings.publicised_frequency = frq
	
	def whoHasRequest(self):
		cs, ok = QInputDialog.getText(self, 'Send a who-has request', 'Callsign:', text=self.callsign_suggestion)
		if ok:
			if cs == '':
				self.whoHasRequest()
			else:
				self.whoHas_window.newRequest(cs)
				settings.session_manager.sendWhoHas(cs)
				self.whoHas_window.show()
				self.callsign_suggestion = cs
		

