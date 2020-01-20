from PyQt5.QtWidgets import QWidget
from ui.notepads import Ui_notepadPane
from session.config import settings


# ---------- Constants ----------

# -------------------------------


class NotepadPane(QWidget, Ui_notepadPane):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.localNotes_textEdit.setPlainText(settings.local_notes)
		self.generalNotes_textEdit.setPlainText(settings.general_notes)
		self.localNotes_textEdit.textChanged.connect(self.saveLocalNotes)
		self.generalNotes_textEdit.textChanged.connect(self.saveGeneralNotes)
	
	def saveGeneralNotes(self):
		settings.general_notes = self.generalNotes_textEdit.toPlainText()
	
	def saveLocalNotes(self):
		settings.local_notes = self.localNotes_textEdit.toPlainText()
	
