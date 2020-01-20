
from PyQt5.QtCore import QObject, QEvent, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, \
			QSizePolicy, QColorDialog, QLineEdit, QPushButton, QToolButton, QDialogButtonBox

from ui.weatherDispWidget import Ui_weatherDispWidget
from ui.quickReference import Ui_quickReference
from ui.xpdrCodeSelector import Ui_xpdrCodeSelectorWidget

from session.env import env
from session.config import settings, PTT_keys

from data.util import some
from data.nav import Airfield, world_navpoint_db, NavpointError
from data.weather import hPa2inHg

from gui.misc import signals, IconFile
from gui.panels.navigator import AirportNavigatorWidget
from gui.graphics.miscGraphics import coloured_square_icon


# ---------- Constants ----------

airportPicker_shortcutToHere = '.'

recognisedValue_lineEdit_styleSheet = 'QLineEdit { color: black; background-color: rgb(200, 255, 200) }' # pale green
unrecognisedValue_lineEdit_styleSheet = 'QLineEdit { color: black; background-color: rgb(255, 200, 200) }' # pale red

quick_ref_disp = 'resources/quick-ref/display-conventions.html'
quick_ref_kbd = 'resources/quick-ref/keyboard-input.html'
quick_ref_mouse = 'resources/quick-ref/mouse-gestures.html'
quick_ref_aliases = 'resources/quick-ref/text-aliases.html'
quick_ref_voice = 'resources/quick-ref/voice-instructions.html'

# -------------------------------



class RadioKeyEventFilter(QObject):
	def eventFilter(self, receiver, event):
		t = event.type()
		if t == QEvent.KeyPress or t == QEvent.KeyRelease:
			#DEBUG('EVENT key=%s, nvk=%s, nsc=%s' % (event.key(), event.nativeVirtualKey(), event.nativeScanCode()))
			try:
				key_number = next(i for i, key in enumerate(PTT_keys) if key == event.key())
				signals.kbdPTT.emit(key_number, t == QEvent.KeyPress)
				return True
			except StopIteration:
				return False
		else:
			return QObject.eventFilter(self, receiver, event)




##------------------------------##
##                              ##
##           AIRPORTS           ##
##                              ##
##------------------------------##

class AirportPicker(QWidget):
	# SIGNALS
	unrecognised = pyqtSignal(str) # Not emitted if an ICAO code is recognised
	recognised = pyqtSignal(Airfield) # Emitted when either set or recognised
	
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.airport_edit = QLineEdit(self)
		self.search_button = QToolButton(self)
		layout = QHBoxLayout(self)
		layout.setSpacing(0)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.airport_edit)
		layout.addWidget(self.search_button)
		self.airport_edit.setClearButtonEnabled(True)
		self.search_button.setToolTip('Search...')
		self.search_button.setIcon(QIcon(IconFile.button_search))
		self.search_button.setFocusPolicy(Qt.ClickFocus)
		self.setFocusProxy(self.airport_edit)
		self.recognised_airport = None
		self.search_button.clicked.connect(self.searchAirportByName)
		self.airport_edit.textEdited.connect(self.tryRecognising)
		self.recognised.connect(lambda ad: self.airport_edit.setToolTip(ad.long_name))
		self.unrecognised.connect(lambda: self.airport_edit.setToolTip(''))
	
	def currentText(self):
		return self.airport_edit.text()
	
	def setEditText(self, txt):
		self.airport_edit.setText(txt)
		self.tryRecognising(txt)
	
	def tryRecognising(self, txt):
		self.recognised_airport = None
		if txt == airportPicker_shortcutToHere and env.airport_data != None:
			txt = settings.location_code
		try:
			self.recognise(world_navpoint_db.findAirfield(txt))
		except NavpointError:
			self.airport_edit.setStyleSheet('' if txt == '' else unrecognisedValue_lineEdit_styleSheet)
			self.unrecognised.emit(txt)

	def searchAirportByName(self):
		init = self.currentText() if self.recognised_airport == None else ''
		dialog = AirportListSearchDialog(self, world_navpoint_db, initNameFilter=init)
		dialog.exec()
		if dialog.result() > 0:
			self.recognise(dialog.selectedAirport())
		self.airport_edit.setFocus()
	
	def selectedFromNavigator(self, ad):
		self.recognise(ad)
		AirportPicker.navigator.hide()
	
	def recognise(self, ad):
		self.airport_edit.setText(ad.code)
		self.airport_edit.setStyleSheet(recognisedValue_lineEdit_styleSheet)
		self.recognised_airport = ad
		self.recognised.emit(ad)



class AirportListSearchDialog(QDialog):
	def __init__(self, parent, nav_db, initCodeFilter=None, initNameFilter=None):
		assert initCodeFilter == None or initNameFilter == None
		QDialog.__init__(self, parent)
		self.resize(350, 300)
		self.setWindowTitle('Airport search')
		self.setWindowIcon(QIcon(IconFile.panel_airportList))
		self.navigator = AirportNavigatorWidget(self, nav_db)
		self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, self)
		layout = QVBoxLayout(self)
		layout.addWidget(self.navigator)
		layout.addWidget(self.button_box)
		self.selected_airport = None
		self.navigator.setAndUpdateFilter(initCodeFilter != None, some(initCodeFilter, some(initNameFilter, '')))
		self.navigator.airportDoubleClicked.connect(self.selectAirport)
		self.button_box.accepted.connect(self.selectAirportFromSelection)
		self.button_box.rejected.connect(self.reject)
	
	def selectAirportFromSelection(self):
		self.selected_airport = self.navigator.selectedAirport()
		if self.selected_airport != None:
			self.accept()
	
	def selectAirport(self, ad):
		self.selected_airport = ad
		self.accept()
	
	def selectedAirport(self):
		return self.selected_airport


class WorldAirportNavigator(QWidget):
	def __init__(self, parent):
		QWidget.__init__(self, parent)
		self.resize(500, 300)
		self.setWindowTitle('World airports')
		self.setWindowIcon(QIcon(IconFile.panel_airportList))
		self.navigator = AirportNavigatorWidget(self, world_navpoint_db)
		self.close_button = QPushButton('Close', self)
		layout = QVBoxLayout(self)
		layout.addWidget(self.navigator)
		layout.addWidget(self.close_button)
		self.navigator.airportDoubleClicked.connect(lambda ad: signals.indicatePoint.emit(ad.coordinates))
		self.close_button.clicked.connect(self.hide)
	
	def showEvent(self, event):
		self.navigator.setFocus()



##----------------------------------------##
##                                        ##
##         RELATED TO TRANSPONDERS        ##
##                                        ##
##----------------------------------------##

class XpdrCodeSelectorWidget(QWidget, Ui_xpdrCodeSelectorWidget):
	codeChanged = pyqtSignal(int)
	
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.setFocusProxy(self.xpdrCode_edit)
		self.updateXPDRranges()
		self.xpdrRange_select.currentIndexChanged.connect(self.selectXpdrRange)
		self.xpdrCode_edit.valueChanged.connect(self.codeChanged.emit)
	
	def updateXPDRranges(self):
		self.xpdrRange_select.setCurrentIndex(0)
		while self.xpdrRange_select.count() > 1:
			self.xpdrRange_select.removeItem(1)
		self.xpdrRange_select.addItems([r.name for r in settings.XPDR_assignment_ranges if r != None])
	
	def selectXpdrRange(self, row):
		if row != 0:
			name = self.xpdrRange_select.itemText(row)
			assignment_range = next(r for r in settings.XPDR_assignment_ranges if r != None and r.name == name)
			self.xpdrCode_edit.setValue(env.nextSquawkCodeAssignment(assignment_range))
			self.xpdrRange_select.setCurrentIndex(0)
			self.xpdrCode_edit.setFocus()
	
	def getSQ(self):
		return self.xpdrCode_edit.value()
	
	def setSQ(self, value):
		return self.xpdrCode_edit.setValue(value)




##------------------------------------##
##                                    ##
##         RELATED TO WEATHER         ##
##                                    ##
##------------------------------------##

class WeatherDispWidget(QWidget, Ui_weatherDispWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
	
	def updateDisp(self, new_weather):
		if new_weather == None:
			self.METAR_info.setText('N/A')
			self.wind_info.setText('N/A')
			self.visibility_info.setText('N/A')
			self.QNH_info.setText('N/A')
		else:
			self.METAR_info.setText(new_weather.METAR())
			self.wind_info.setText(new_weather.readWind())
			self.visibility_info.setText(new_weather.readVisibility())
			qnh = new_weather.QNH()
			if qnh == None:
				self.QNH_info.setText('N/A')
			else:
				self.QNH_info.setText('%d hPa, %.2f inHg' % (qnh, hPa2inHg * qnh))
		



##-------------------------------------##
##                                     ##
##            COLOUR PICKER            ##
##                                     ##
##-------------------------------------##

class ColourPicker(QWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.pick_button = QToolButton(self)
		self.pick_button.setText('Pick...')
		self.clear_button = QToolButton(self)
		self.clear_button.setText('Clear')
		self.clear_button.setAutoRaise(True)
		layout = QHBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.pick_button)
		layout.addWidget(self.clear_button)
		self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
		self.colour_choice = None
		self.clear_button.clicked.connect(self.clearColour)
		self.pick_button.clicked.connect(self.pickNewColour)
		self.updateColourIcon()
	
	def updateColourIcon(self):
		if self.colour_choice == None:
			self.pick_button.setIcon(QIcon())
			self.clear_button.hide()
		else:
			self.pick_button.setIcon(coloured_square_icon(self.colour_choice))
			self.clear_button.show()
	
	def setChoice(self, colour):
		self.colour_choice = colour
		self.updateColourIcon()
	
	def getChoice(self):
		return self.colour_choice
	
	def pickNewColour(self):
		colour = QColorDialog.getColor(parent=self, title='Pick radar contact colour', initial=some(self.colour_choice, Qt.white))
		if colour.isValid():
			self.setChoice(colour)
	
	def clearColour(self):
		self.colour_choice = None
		self.updateColourIcon()
		




##------------------------------------##
##                                    ##
##           QUICK REFERENCE          ##
##                                    ##
##------------------------------------##

class QuickReference(QWidget, Ui_quickReference):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		with open(quick_ref_disp) as f:
			self.disp_pane.setHtml(f.read())
		with open(quick_ref_kbd) as f:
			self.kbd_pane.setHtml(f.read())
		with open(quick_ref_mouse) as f:
			self.mouse_pane.setHtml(f.read())
		with open(quick_ref_aliases) as f:
			self.aliases_pane.setHtml(f.read())
		with open(quick_ref_voice) as f:
			self.voice_pane.setHtml(f.read())

