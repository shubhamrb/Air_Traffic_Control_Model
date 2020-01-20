from PyQt5.QtWidgets import QDialog
from PyQt5.QtGui import QTransform

from ui.positionDrawingDialog import Ui_positionDrawingDialog


# ---------- Constants ----------

fine_step_NM = .1
gross_step_NM = 2

# -------------------------------



class PositionBgImgDialog(QDialog, Ui_positionDrawingDialog):
	def __init__(self, graphics_items, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.items = graphics_items
		self.updateDisplay()
		self.moveUp_button.clicked.connect(lambda: self.moveImages(0, -1))
		self.moveDown_button.clicked.connect(lambda: self.moveImages(0, 1))
		self.moveLeft_button.clicked.connect(lambda: self.moveImages(-1, 0))
		self.moveRight_button.clicked.connect(lambda: self.moveImages(1, 0))
		self.increaseWidth_button.clicked.connect(lambda: self.scaleImages(1, 0))
		self.reduceWidth_button.clicked.connect(lambda: self.scaleImages(-1, 0))
		self.increaseHeight_button.clicked.connect(lambda: self.scaleImages(0, 1))
		self.reduceHeight_button.clicked.connect(lambda: self.scaleImages(0, -1))
	
	def tuningStep(self):
		return fine_step_NM if self.fineTuning_tickBox.isChecked() else gross_step_NM
	
	def updateDisplay(self):
		if self.items == []:
			txt = 'Make at least one image visible!'
		else:
			txt = ''
			for item in self.items:
				nw = item.NWcoords()
				se = item.SEcoords()
				txt += '\n%s\n' % item.title
				txt += 'NW: %s\n' % nw.toString()
				txt += 'SE: %s\n' % se.toString()
		self.central_text_area.setPlainText(txt)
	
	def moveImages(self, kx, ky):
		for item in self.items:
			item.moveBy(kx * self.tuningStep(), ky * self.tuningStep())
		self.updateDisplay()
	
	def scaleImages(self, kx, ky):
		for item in self.items:
			rect = item.boundingRect()
			scale = QTransform.fromScale(1 + kx * self.tuningStep() / rect.width(), 1 + ky * self.tuningStep() / rect.height())
			item.setTransform(scale, combine=True)
		self.updateDisplay()


