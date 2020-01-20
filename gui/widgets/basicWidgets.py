
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox, QInputDialog, \
		QCompleter, QComboBox, QToolButton, QPushButton, QSpinBox

from session.env import env

from gui.misc import IconFile

from data.strip import Strip, strip_mime_type
from data.utc import timestr
from data.db import known_aircraft_types
from data.comms import CommFrequency


# ---------- Constants ----------

initial_alarm_clock_timeout = 2 # minutes

# -------------------------------



##-------------------------------------##
##                                     ##
##          FREQUENCY CHOOSER          ##
##                                     ##
##-------------------------------------##


class FrequencyPickCombo(QComboBox):
	frequencyChanged = pyqtSignal(CommFrequency)
	
	def __init__(self, parent=None):
		QComboBox.__init__(self, parent)
		self.setEditable(True)
		self.lineEdit().returnPressed.connect(self.selectFrequency)
		self.currentIndexChanged.connect(self.selectFrequency)
	
	def addFrequencies(self, frqlst):
		self.addItems(['%s  %s' % frq_descr_pair for frq_descr_pair in frqlst])
	
	def selectFrequency(self):
		frq = self.getFrequency()
		if frq == None:
			QMessageBox.critical(self, 'Invalid frequency', 'Line entry does not start with a valid frequency string.')
		else:
			self.frequencyChanged.emit(frq)
		
	def getFrequency(self):
		try:
			return CommFrequency(self.currentText().split(maxsplit=1)[0])
		except (IndexError, ValueError):
			return None




	

##-------------------------------------##
##                                     ##
##        AIRCRAFT TYPE CHOOSER        ##
##                                     ##
##-------------------------------------##


class AircraftTypeCombo(QComboBox):	
	def __init__(self, parent=None):
		QComboBox.__init__(self, parent)
		items = known_aircraft_types() # set
		items.add('ZZZZ')
		self.addItems(sorted(items))
		self.setEditable(True)
		self.completer().setCompletionMode(QCompleter.PopupCompletion)
		self.completer().setFilterMode(Qt.MatchContains)
	
	def setAircraftFilter(self, pred):
		new_entries = [t for t in known_aircraft_types() if pred(t)]
		new_entries.sort()
		self.clear()
		self.addItems(new_entries)
	
	def getAircraftType(self):
		value = self.currentText()
		return None if value == '' else value





##----------------------------------------##
##                                        ##
##         RELATED TO TRANSPONDERS        ##
##                                        ##
##----------------------------------------##


class XpdrCodeSpinBox(QSpinBox):
	def __init__(self, parent=None):
		QSpinBox.__init__(self, parent)
		self.setDisplayIntegerBase(8)
		self.setMaximum(0o7777)
		self.setWrapping(True)
	
	def textFromValue(self, sq):
		return '%04o' % sq




##------------------------------##
##                              ##
##           BUTTONS            ##
##                              ##
##------------------------------##


class ShelfButtonWidget(QPushButton):
	# SIGNAL
	stripDropped = pyqtSignal(Strip)
	
	def __init__(self, parent=None):
		QPushButton.__init__(self, parent)
		#self.setStyleSheet('QPushButton { background-image: url(%s) }' % IconFile.button_shelf)
		self.setIcon(QIcon(IconFile.button_shelf))
		self.setToolTip('Strip shelf')
		self.setFlat(True)
		self.setAcceptDrops(True)
	
	def dragEnterEvent(self, event):
		if event.mimeData().hasFormat(strip_mime_type):
			event.acceptProposedAction()
	
	def dropEvent(self, event):
		mime_data = event.mimeData()
		if mime_data.hasFormat(strip_mime_type):
			self.stripDropped.emit(env.strips.fromMimeDez(mime_data))
			event.acceptProposedAction()



class AlarmClockButton(QToolButton):
	# SIGNAL
	alarm = pyqtSignal(str)
	
	def __init__(self, name, parent=None):
		QToolButton.__init__(self, parent)
		self.setIcon(QIcon(IconFile.button_alarmClock))
		self.setCheckable(True)
		self.name = name
		self.prev_timeout = initial_alarm_clock_timeout
		self.resetButton()
		self.timer = QTimer(self)
		self.timer.setSingleShot(True)
		self.timer.timeout.connect(lambda: self.alarm.emit(self.name))
		self.timer.timeout.connect(self.resetButton)
		self.clicked.connect(self.buttonClicked)
	
	def timerIsRunning(self):
		return self.timer.isActive()
	
	def buttonClicked(self):
		if self.timerIsRunning():
			self.timer.stop()
			self.resetButton()
		else:
			self.setTimer()
	
	def setTimer(self):
		timeout, ok = QInputDialog.getInt(self, \
			'Alarm clock %s' % self.name, 'Timeout in minutes:', value=self.prev_timeout, min=1, max=60)
		if ok:
			self.setToolTip('Timer %s started at %s for %d min' % (self.name, timestr(seconds=True), timeout))
			self.timer.start(timeout * 60 * 1000)
			self.prev_timeout = timeout
			self.setChecked(True)
		elif not self.timerIsRunning():
			self.resetButton()
	
	def resetButton(self):
		self.setToolTip('Alarm clock %s' % self.name)
		self.setChecked(False)


