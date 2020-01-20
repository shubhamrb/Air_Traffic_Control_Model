from os import path

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QUrl
from PyQt5.QtGui import QPixmap, QIcon, QColor
from PyQt5.QtWidgets import QWidget, QMenu, QAction
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from ui.notifier import Ui_notifierFrame

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.nav import Navpoint
from data.strip import received_from_detail, assigned_SQ_detail
from data.comms import CpdlcMessage
from data.utc import now, rel_datetime_str
from data.fpl import FPL

from gui.misc import signals, IconFile


# ---------- Constants ----------

sounds_directory = 'resources/sounds'
icons_directory = 'resources/pixmap'

# -------------------------------


class Notification:
	types = GUI_INFO, ALARM_TIMEOUT, UNRECOGNISED_VOICE_INSTR, \
			ATC_CONNECTED, WEATHER_UPDATE, FPL_FILED, RADIO_CHAT_MSG, ATC_CHAT_MSG, \
			RADAR_IDENTIFICATION, LOST_LINKED_CONTACT, STRIP_RECEIVED, STRIP_AUTO_PRINTED, \
			EMG_SQUAWK, RWY_INCURSION, CONFLICT_WARNING, SEPARATION_INCIDENT, \
			CPDLC_MSG, CPDLC_PROBLEM = range(18)
	
	def __init__(self, notification_type, time, msg, action):
		self.t = notification_type
		self.time = time
		self.msg = msg
		self.double_click_function = action
	
	def tstr(t):
		return {
			Notification.GUI_INFO: 'GUI message',
			Notification.ALARM_TIMEOUT: 'Alarm clock time-out',
			Notification.UNRECOGNISED_VOICE_INSTR: 'Unrecognised voice instruction',
			Notification.ATC_CONNECTED: 'New ATC connection',
			Notification.WEATHER_UPDATE: 'Primary weather update',
			Notification.FPL_FILED: 'FPL filed for location',
			Notification.RADIO_CHAT_MSG: 'Incoming radio chat message',
			Notification.ATC_CHAT_MSG: 'Incoming ATC text message',
			Notification.RADAR_IDENTIFICATION: 'Radar identification',
			Notification.LOST_LINKED_CONTACT: 'Linked radar contact lost',
			Notification.STRIP_RECEIVED: 'Strip received',
			Notification.STRIP_AUTO_PRINTED: 'Strip auto-printed',
			Notification.EMG_SQUAWK: 'Emergency squawk',
			Notification.RWY_INCURSION: 'Runway incursion',
			Notification.CONFLICT_WARNING: 'Route conflict',
			Notification.SEPARATION_INCIDENT: 'Separation incident',
			Notification.CPDLC_MSG: 'CPDLC connection or request',
			Notification.CPDLC_PROBLEM: 'CPDLC dialogue problem'
		}[t]


icon_files = { # If given, the messages will be logged in the notification table.
	Notification.GUI_INFO: 'info.png',
	Notification.ALARM_TIMEOUT: 'stopwatch.png',
	Notification.ATC_CONNECTED: 'control-TWR.png',
	Notification.WEATHER_UPDATE: 'weather.png',
	Notification.FPL_FILED: 'FPLicon.png',
	Notification.RADAR_IDENTIFICATION: 'radar.png',
	Notification.LOST_LINKED_CONTACT: 'contactLost.png',
	Notification.STRIP_RECEIVED: 'envelope.png',
	Notification.STRIP_AUTO_PRINTED: 'printer.png',
	Notification.EMG_SQUAWK: 'planeEMG.png',
	Notification.RWY_INCURSION: 'runway-incursion.png',
	Notification.CONFLICT_WARNING: 'routeConflict.png',
	Notification.SEPARATION_INCIDENT: 'nearMiss.png',
	Notification.CPDLC_MSG: 'cpdlc.png',
	Notification.CPDLC_PROBLEM: 'cpdlc.png'
} # No log for: Notification.UNRECOGNISED_VOICE_INSTR, Notification.RADIO_CHAT_MSG, Notification.ATC_CHAT_MSG


sound_files = { # If given, a sound can be toggled for this type of notification.
	Notification.ALARM_TIMEOUT: 'timeout.mp3',
	Notification.UNRECOGNISED_VOICE_INSTR: 'loBuzz.mp3',
	Notification.ATC_CONNECTED: 'aeroplaneDing.mp3',
	Notification.WEATHER_UPDATE: 'chime.mp3',
	Notification.RADIO_CHAT_MSG: 'typeWriter.mp3',
	Notification.ATC_CHAT_MSG: 'hiClick.mp3',
	Notification.RADAR_IDENTIFICATION: 'detectorBeep.mp3',
	Notification.LOST_LINKED_CONTACT: 'turnedOff.mp3',
	Notification.STRIP_RECEIVED: 'loClick.mp3',
	Notification.STRIP_AUTO_PRINTED: 'printer.mp3',
	Notification.EMG_SQUAWK: 'sq-buzz.mp3',
	Notification.RWY_INCURSION: 'alarm.mp3',
	Notification.CONFLICT_WARNING: 'alarmHalf.mp3',
	Notification.SEPARATION_INCIDENT: 'alarm.mp3',
	Notification.CPDLC_MSG: 'phoneDial.mp3',
	Notification.CPDLC_PROBLEM: 'phoneTone.mp3'
} # No sound notification for: Notification.GUI_INFO, Notification.FPL_FILED


def mkSound(file_base_name):
	return QMediaContent(QUrl.fromLocalFile(path.abspath(path.join(sounds_directory, file_base_name))))

wilco_beep = mkSound('hiBuzz.mp3')

notification_sound_base = { t: mkSound(f) for t, f in sound_files.items() }




default_sound_notifications = {
	Notification.ALARM_TIMEOUT, Notification.LOST_LINKED_CONTACT, Notification.UNRECOGNISED_VOICE_INSTR,
	Notification.ATC_CONNECTED, Notification.WEATHER_UPDATE, Notification.STRIP_RECEIVED,
	Notification.STRIP_AUTO_PRINTED, Notification.ATC_CHAT_MSG, Notification.EMG_SQUAWK,
	Notification.RWY_INCURSION, Notification.CONFLICT_WARNING, Notification.SEPARATION_INCIDENT,
	Notification.CPDLC_MSG, Notification.CPDLC_PROBLEM
}




class NotificationHistoryModel(QAbstractTableModel):
	columns = ['Time', 'Message']

	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.history = []

	def rowCount(self, parent=None):
		return len(self.history)

	def columnCount(self, parent):
		return len(NotificationHistoryModel.columns)

	def data(self, index, role):
		col = index.column()
		notification = self.history[index.row()]
		if role == Qt.DisplayRole:
			if col == 0:
				return rel_datetime_str(notification.time, seconds=True)
			if col == 1:
				return notification.msg
		elif role == Qt.DecorationRole:
			if col == 0:
				try:
					pixmap = QPixmap(path.join(icons_directory, icon_files[notification.t]))
					return QIcon(pixmap)
				except KeyError:
					pass # No decoration for this notification type

	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return NotificationHistoryModel.columns[section]
	
	def addNotification(self, t, msg, dbl_click_function):
		position = self.rowCount()
		self.beginInsertRows(QModelIndex(), position, position)
		self.history.insert(position, Notification(t, now(), msg, dbl_click_function))
		self.endInsertRows()
		return True

	def clearNotifications(self):
		self.beginRemoveRows(QModelIndex(), 0, self.rowCount() - 1)
		self.history.clear()
		self.endRemoveRows()
		return True




class NotifierFrame(QWidget, Ui_notifierFrame):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.cleanUp_button.setIcon(QIcon(IconFile.button_clear))
		self.table_model = NotificationHistoryModel(self)
		self.notification_table.setModel(self.table_model)
		if settings.sound_notifications == None:
			settings.sound_notifications = default_sound_notifications
		# In case loading the settings inserted bad values:
		settings.sound_notifications = { t for t in settings.sound_notifications if t in notification_sound_base }
		self.media_player = QMediaPlayer()
		self.notification_table.doubleClicked.connect(self.notificationDoubleClicked)
		self.cleanUp_button.clicked.connect(self.table_model.clearNotifications)
		# Menu
		self.PTTturnsOffSounds_action = QAction('Mute on PTT (recommended if no headset)', self)
		self.PTTturnsOffSounds_action.setCheckable(True)
		self.PTTturnsOffSounds_action.setChecked(settings.PTT_mutes_sound_notifications)
		self.PTTturnsOffSounds_action.toggled.connect(self.togglePTTmute)
		self.sound_menu = QMenu()
		self.sound_menu.addAction(self.PTTturnsOffSounds_action)
		self.sound_menu.addSeparator()
		for t in Notification.types: # iterate on this to control order of entries in menu
			if t in notification_sound_base: # only notifications with sounds go in the sound toggle menu
				action = QAction(Notification.tstr(t), self)
				action.setCheckable(True)
				self.sound_menu.addAction(action)
				action.setChecked(t in settings.sound_notifications)
				action.toggled.connect(lambda b: self.enableSound(t, b))
		self.sounds_menuButton.setMenu(self.sound_menu)
		# Notification signals
		env.radar.emergencySquawk.connect(self.catchEmergencySquawk)
		env.radar.pathConflict.connect(lambda: self.notify(Notification.CONFLICT_WARNING, 'Anticipated conflict'))
		env.radar.nearMiss.connect(lambda: self.notify(Notification.SEPARATION_INCIDENT, 'Loss of separation!'))
		env.radar.runwayIncursion.connect(self.catchRwyIncursion)
		signals.cpdlcAcftConnected.connect(self.catchCpdlcInit)
		signals.cpdlcMessageReceived.connect(self.catchCpdlcMessage)
		signals.cpdlcProblem.connect(self.catchCpdlcProblem)
		signals.sessionStarted.connect(self.catchSessionStarted)
		signals.sessionEnded.connect(lambda: self.notify(Notification.GUI_INFO, 'Session ended.'))
		signals.sessionPaused.connect(lambda: self.notify(Notification.GUI_INFO, 'Simulation paused.'))
		signals.sessionResumed.connect(lambda: self.notify(Notification.GUI_INFO, 'Simulation resumed.'))
		signals.newWeather.connect(self.catchNewWeather)
		signals.voiceMsgNotRecognised.connect(lambda: self.notify(Notification.UNRECOGNISED_VOICE_INSTR, 'Voice instruction not recognised.'))
		signals.newATC.connect(self.catchNewATC)
		signals.newFPL.connect(self.catchNewFlightPlan)
		signals.stripAutoPrinted.connect(self.catchStripAutoPrinted)
		signals.controlledContactLost.connect(self.catchLostLinkedContact)
		signals.incomingRadioChatMsg.connect(lambda msg: self.notify(Notification.RADIO_CHAT_MSG, None))
		signals.incomingAtcTextMsg.connect(self.catchIncomingAtcMsg)
		signals.aircraftIdentification.connect(self.catchAircraftIdentification)
		signals.receiveStrip.connect(self.catchStripReceived)
		signals.wilco.connect(lambda: self.playSound(wilco_beep))
	
	def playSound(self, sound):
		self.media_player.setMedia(sound)
		self.media_player.play()
	
	def notify(self, t, msg, dblClick=None):
		if msg != None:
			signals.statusBarMsg.emit(msg)
			if t in icon_files:
				self.table_model.addNotification(t, msg, dblClick)
				self.notification_table.scrollToBottom()
		if settings.notification_sounds_enabled and not settings.session_start_sound_lock \
				and t in settings.sound_notifications \
				and not (settings.transmitting_radio and settings.PTT_mutes_sound_notifications):
			self.playSound(notification_sound_base[t])
	
	def notifyAlarmClockTimedOut(self, timer):
		self.notify(Notification.ALARM_TIMEOUT, 'Alarm clock %s timed out' % timer)
	
	## USER ACTIONS/TOGGLES
	
	def enableSound(self, t, toggle):
		if toggle:
			settings.sound_notifications.add(t)
		else:
			settings.sound_notifications.remove(t)
	
	def togglePTTmute(self, toggle):
		settings.PTT_mutes_sound_notifications = toggle
	
	def notificationDoubleClicked(self):
		try:
			notification = self.table_model.history[self.notification_table.selectedIndexes()[0].row()]
		except IndexError:
			return
		if notification.double_click_function != None:
			notification.double_click_function()
	
	## REACTING TO GUI SIGNALS
	
	def catchNewATC(self, callsign):
		if settings.session_manager.session_type == SessionType.FLIGHTGEAR_MP:
			self.notify(Notification.ATC_CONNECTED, '%s connected' % callsign)
	
	def catchIncomingAtcMsg(self, msg):
		if msg.isPrivate():
			self.notify(Notification.ATC_CHAT_MSG, '%s: "%s"' % (msg.sender(), msg.txtOnly()))
		elif settings.ATC_chatroom_msg_notifications:
			self.notify(Notification.ATC_CHAT_MSG, 'ATC chat room message')
	
	def catchCpdlcInit(self, callsign):
		if settings.session_manager.session_type != SessionType.TEACHER:
			f = lambda cs=callsign: signals.cpdlcWindowRequest.emit(cs)
			self.notify(Notification.CPDLC_MSG, 'Data link established with %s' % callsign, dblClick=f)
	
	def catchCpdlcMessage(self, callsign, msg):
		f = lambda cs=callsign: signals.cpdlcWindowRequest.emit(cs)
		if settings.session_manager.session_type == SessionType.TEACHER:
			self.notify(Notification.CPDLC_MSG, 'CPDLC transmission to %s' % callsign, dblClick=f)
		elif msg.type() == CpdlcMessage.FREE_TEXT:
			self.notify(Notification.CPDLC_MSG, 'CPDLC text message from %s' % callsign, dblClick=f)
	
	def catchCpdlcProblem(self, callsign, pb):
		f = lambda cs=callsign: signals.cpdlcWindowRequest.emit(cs)
		self.notify(Notification.CPDLC_PROBLEM, 'CPDLC problem with %s' % callsign, dblClick=f)
	
	def catchLostLinkedContact(self, strip, pos):
		cs = strip.callsign(fpl=True)
		msg = 'Radar contact lost'
		if cs != None:
			msg += ' for ' + cs
		msg += ' ' + map_loc_str(pos)
		f = lambda coords=pos: signals.indicatePoint.emit(coords)
		self.notify(Notification.LOST_LINKED_CONTACT, msg, dblClick=f)
	
	def catchAircraftIdentification(self, strip, acft, modeS):
		if strip.linkedAircraft() is not acft: # could already be hard linked if XPDR was turned off and back on (avoid too many signals)
			if modeS:
				msg = 'Callsign %s identified (mode S)' % strip.lookup(FPL.CALLSIGN)
			else:
				msg = 'XPDR code %04o identified' % strip.lookup(assigned_SQ_detail)
			f = lambda coords=acft.coords(): signals.indicatePoint.emit(coords)
			self.notify(Notification.RADAR_IDENTIFICATION, msg, dblClick=f)
	
	def catchStripReceived(self, strip):
		fromATC = strip.lookup(received_from_detail)
		if fromATC != None:
			self.notify(Notification.STRIP_RECEIVED, 'Strip received from %s' % fromATC)
	
	def catchStripAutoPrinted(self, strip, reason):
		msg = 'Strip printed'
		cs = strip.callsign(fpl=True)
		if cs != None:
			msg += ' for ' + cs
		if reason != None:
			msg += '; ' + reason
		self.notify(Notification.STRIP_AUTO_PRINTED, msg)
	
	def catchSessionStarted(self):
		txt = {
				SessionType.SOLO: 'Solo session started',
				SessionType.FLIGHTGEAR_MP: 'FlightGear multi-player connected',
				SessionType.STUDENT: 'Student session beginning',
				SessionType.TEACHER: 'Teacher session beginning'
			}[settings.session_manager.session_type]
		self.notify(Notification.GUI_INFO, txt)
	
	def catchNewWeather(self, station, weather):
		if station == settings.primary_METAR_station:
			self.notify(Notification.WEATHER_UPDATE, 'Weather update: %s' % weather.METAR())
	
	def catchNewFlightPlan(self, new_fpl):
		if new_fpl[FPL.ICAO_DEP] == settings.location_code or new_fpl[FPL.ICAO_ARR] == settings.location_code: #STYLE use findAirfield?
			f = lambda fpl=new_fpl: signals.FPLeditRequest.emit(fpl)
			self.notify(Notification.FPL_FILED, 'FPL filed for %s' % settings.location_code, dblClick=f)
	
	def catchEmergencySquawk(self, acft):
		f = lambda coords=acft.coords(): signals.indicatePoint.emit(coords)
		self.notify(Notification.EMG_SQUAWK, 'Aircraft squawking emergency', dblClick=f)
	
	def catchRwyIncursion(self, phyrwy, acft):
		rwy = env.airport_data.physicalRunwayNameFromUse(phyrwy)
		f = lambda coords=acft.coords(): signals.indicatePoint.emit(coords)
		self.notify(Notification.RWY_INCURSION, 'Runway %s incursion!' % rwy, dblClick=f)





def map_loc_str(pos):
	if env.pointOnMap(pos):
		return ' near %s' % env.navpoints.findClosest(pos)
	else:
		return ' far %s' % env.radarPos().headingTo(pos).approxCardinal(True)
