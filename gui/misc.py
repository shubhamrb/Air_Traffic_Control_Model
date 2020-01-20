
from datetime import timedelta

from PyQt5.QtCore import pyqtSignal, QObject, QTimer

from data.acft import Aircraft
from data.strip import Strip, assigned_heading_detail, assigned_altitude_detail, assigned_speed_detail, assigned_SQ_detail
from data.fpl import FPL
from data.coords import EarthCoords
from data.params import Heading, Speed
from data.nav import Navpoint
from data.comms import ChatMessage, CpdlcMessage
from data.instruction import Instruction
from data.weather import Weather

from session.config import settings
from session.env import env


# ---------- Constants ----------

# -------------------------------




##-----------------------------------##
##                                   ##
##          GUI ENVIRONMENT          ##
##                                   ##
##-----------------------------------##

class IconFile:
	action_generalSettings = 'resources/pixmap/tools.png'
	action_sessionSettings = 'resources/pixmap/toolsInPlay.png'
	action_runwayUse = 'resources/pixmap/runway-use.png'
	action_newStrip = 'resources/pixmap/newStrip.png'
	action_newLinkedStrip = 'resources/pixmap/newLinkedStrip.png'
	action_newFPL = 'resources/pixmap/newFPL.png'
	action_newLinkedFPL = 'resources/pixmap/newLinkedFPL.png'
	action_newRack = 'resources/pixmap/newRack.png'
	action_newRackPanel = 'resources/pixmap/newRackPanel.png'
	action_newRadarScreen = 'resources/pixmap/newRadarScreen.png'
	action_newLooseStripBay = 'resources/pixmap/newLooseStripBay.png'
	action_popOutWindow = 'resources/pixmap/popOutWindow.png'
	action_reclaimWindows = 'resources/pixmap/reclaimWindows.png'
	
	option_primaryRadar = 'resources/pixmap/primary-radar.png'
	option_approachSpacingHints = 'resources/pixmap/spacing-hints.png'
	option_runwayOccupationMonitor = 'resources/pixmap/runway-incursion.png'
	option_routeConflictWarnings = 'resources/pixmap/routeConflict.png'
	option_identificationAssistant = 'resources/pixmap/radar-identification.png'

	panel_envInfo = 'resources/pixmap/info.png'
	panel_unitConv = 'resources/pixmap/calculator.png'
	panel_airportList = 'resources/pixmap/AD.png'
	panel_teaching = 'resources/pixmap/teaching.png'
	panel_ATCs = 'resources/pixmap/handshake.png'
	panel_CPDLC = 'resources/pixmap/cpdlc.png'
	panel_atcChat = 'resources/pixmap/ATC-chat.png'
	panel_FPLs = 'resources/pixmap/FPLicon.png'
	panel_instructions = 'resources/pixmap/instruction.png'
	panel_looseBay = 'resources/pixmap/looseStrips.png'
	panel_navigator = 'resources/pixmap/compass.png'
	panel_notepads = 'resources/pixmap/notepad.png'
	panel_notifications = 'resources/pixmap/lightBulb.png'
	panel_radarScreen = 'resources/pixmap/radar.png'
	panel_radios = 'resources/pixmap/radio.png'
	panel_runwayBox = 'resources/pixmap/strip-on-rwy.png'
	panel_selInfo = 'resources/pixmap/plane.png'
	panel_racks = 'resources/pixmap/rack.png'
	panel_txtChat = 'resources/pixmap/chat.png'
	panel_twrView = 'resources/pixmap/control-TWR.png'
	panel_weather = 'resources/pixmap/weather.png'

	button_view = 'resources/pixmap/eye.png'
	button_clear = 'resources/pixmap/sweep.png'
	button_search = 'resources/pixmap/magnifying-glass.png'
	button_save = 'resources/pixmap/floppy-disk.png'
	button_bin = 'resources/pixmap/bin.png'
	button_shelf = 'resources/pixmap/shelf.png'
	button_lockRadar = 'resources/pixmap/lock.png'
	button_alarmClock = 'resources/pixmap/stopwatch.png'
	
	pixmap_strip = 'resources/pixmap/strip.png'
	pixmap_strip_recycled = 'resources/pixmap/recycle.png'
	pixmap_strip_received = 'resources/pixmap/envelope.png'
	pixmap_strip_printed = 'resources/pixmap/printer.png'




class SignalCentre(QObject):
	selectionChanged = pyqtSignal()
	stripInfoChanged = pyqtSignal()
	statusBarMsg = pyqtSignal(str)
	sessionStarted = pyqtSignal()
	sessionEnded = pyqtSignal()
	sessionPaused = pyqtSignal()
	sessionResumed = pyqtSignal()
	fastClockTick = pyqtSignal()
	slowClockTick = pyqtSignal()
	aircraftKilled = pyqtSignal(Aircraft)
	towerViewProcessToggled = pyqtSignal(bool) # True=started; False=finished
	systemSettingsChanged = pyqtSignal()
	generalSettingsChanged = pyqtSignal()
	soloSessionSettingsChanged = pyqtSignal()
	localSettingsChanged = pyqtSignal()
	runwayUseChanged = pyqtSignal()
	rackEdited = pyqtSignal(str, str) # old name, new name
	hdgDistMeasured = pyqtSignal(Heading, float) # heading, distance measured with RMB tool
	rackVisibilityTaken = pyqtSignal(list) # racks made visible in the signalling rack panel
	rackVisibilityLost = pyqtSignal(list) # racks in closed view
	backgroundImagesReloaded = pyqtSignal()
	colourConfigReloaded = pyqtSignal()
	mainWindowClosing = pyqtSignal()
	kbdPTT = pyqtSignal(int, bool)   # kbd PTT key number, mic PTT
	rdfSignalChanged = pyqtSignal()
	
	indicatePoint = pyqtSignal(EarthCoords)
	navpointClick = pyqtSignal(Navpoint)
	pkPosClick = pyqtSignal(str)
	specialTool = pyqtSignal(EarthCoords, Heading)
	voiceMsgRecognised = pyqtSignal(list, list) # callsign tokens used, recognised instructions
	voiceMsgNotRecognised = pyqtSignal()
	wilco = pyqtSignal()
	
	weatherUpdateRequest = pyqtSignal()
	fplUpdateRequest = pyqtSignal()
	newATC = pyqtSignal(str) # callsign
	newFPL = pyqtSignal(FPL)
	stripAutoPrinted = pyqtSignal(Strip, str) # str is DEP/ARR + time reason for auto-print
	controlledContactLost = pyqtSignal(Strip, EarthCoords)
	aircraftIdentification = pyqtSignal(Strip, Aircraft, bool) # bool True if mode S identification
	newWeather = pyqtSignal(str, Weather) # str = the station with new weather
	voiceMsg = pyqtSignal(Aircraft, str)
	chatInstructionSuggestion = pyqtSignal(str, str, bool) # dest callsign, instr message, send immediately
	incomingRadioChatMsg = pyqtSignal(ChatMessage)
	incomingAtcTextMsg = pyqtSignal(ChatMessage)
	incomingContactClaim = pyqtSignal(str, str) # sender, ACFT callsign
	cpdlcAcftConnected = pyqtSignal(str) # connected callsign
	cpdlcAcftDisconnected = pyqtSignal(str) # disconnected callsign
	cpdlcMessageReceived = pyqtSignal(str, CpdlcMessage) # ACFT callsign, message
	cpdlcProblem = pyqtSignal(str, str) # ACFT callsign, problem description
	cpdlcWindowRequest = pyqtSignal(str) # ACFT callsign
	
	privateAtcChatRequest = pyqtSignal(str)
	openShelfRequest = pyqtSignal()
	stripRecall = pyqtSignal(Strip)
	stripEditRequest = pyqtSignal(Strip)
	FPLeditRequest = pyqtSignal(FPL)
	newLinkedFPLrequest = pyqtSignal(Strip)
	launchADmode = pyqtSignal(str)
	launchCTRmode = pyqtSignal(str, str)
	receiveStrip = pyqtSignal(Strip)
	handoverFailure = pyqtSignal(Strip, str)
	
	def __init__(self):
		QObject.__init__(self)


signals = SignalCentre()






class Selection:
	def __init__(self):
		self.acft = None
		self.strip = None
		self.fpl = None
	
	def none(self):
		return self.acft == None and self.strip == None and self.fpl == None
	
	def deselect(self):
		self.acft = self.strip = self.fpl = None
		signals.selectionChanged.emit()
		
	def selectStrip(self, select):
		self.strip = select
		self.fpl = self.strip.linkedFPL()
		self.acft = self.strip.linkedAircraft()
		signals.selectionChanged.emit()
		
	def selectAircraft(self, select):
		self.acft = select
		self.strip = env.linkedStrip(self.acft)
		if self.strip == None:
			self.fpl = None
		else:
			self.fpl = self.strip.linkedFPL()
		signals.selectionChanged.emit()
		
	def selectFPL(self, select):
		self.fpl = select
		self.strip = env.linkedStrip(self.fpl)
		if self.strip == None:
			self.acft = None
		else:
			self.acft = self.strip.linkedAircraft()
		signals.selectionChanged.emit()
	
	def selectedCallsign(self):
		if self.strip == None:
			if self.acft == None:
				if self.fpl == None:
					return None
				else:
					return self.fpl[FPL.CALLSIGN]
			else:
				return self.acft.xpdrCallsign()
		else:
			if self.strip.callsign(fpl=False) == None:
				if self.acft == None:
					return self.strip.callsign(fpl=True)
				else:
					return self.acft.xpdrCallsign()
			else:
				return self.strip.callsign(fpl=False)
	
	def linkAircraft(self, acft):
		if self.strip != None and self.strip.linkedAircraft() == None and env.linkedStrip(acft) == None:
			self.strip.linkAircraft(acft)
			if settings.strip_autofill_on_ACFT_link:
				self.strip.fillFromXPDR()
			signals.stripInfoChanged.emit()
			self.selectAircraft(acft)

	def unlinkAircraft(self, acft):
		if self.strip != None and self.strip.linkedAircraft() is acft:
			self.strip.linkAircraft(None)
			signals.stripInfoChanged.emit()
			self.selectStrip(self.strip)
	
	def writeStripAssignment(self, instr):
		if self.strip != None:
			# heading assignment
			if instr.type == Instruction.VECTOR_HDG:
				self.strip.writeDetail(assigned_heading_detail, instr.arg)
			elif instr.type in [Instruction.VECTOR_DCT, Instruction.FOLLOW_ROUTE, Instruction.HOLD, \
					Instruction.INTERCEPT_NAV, Instruction.INTERCEPT_LOC, Instruction.CLEARED_APP, Instruction.CLEARED_TO_LAND]:
				self.strip.writeDetail(assigned_heading_detail, None)
			# altitude assignment
			if instr.type == Instruction.VECTOR_ALT:
				self.strip.writeDetail(assigned_altitude_detail, instr.arg)
			elif instr.type in [Instruction.CLEARED_APP, Instruction.CLEARED_TO_LAND]:
				self.strip.writeDetail(assigned_altitude_detail, None)
			# speed assignment
			if instr.type == Instruction.VECTOR_SPD:
				self.strip.writeDetail(assigned_speed_detail, instr.arg)
			elif instr.type in [Instruction.CANCEL_VECTOR_SPD, Instruction.HOLD, Instruction.CLEARED_TO_LAND]:
				self.strip.writeDetail(assigned_speed_detail, None)
			# transponder assignment
			if instr.type == Instruction.SQUAWK:
				self.strip.writeDetail(assigned_SQ_detail, instr.arg)
			signals.stripInfoChanged.emit()
	
	def __str__(self):
		return '{strip:%s, fpl:%s, acft:%s}' % (self.strip, self.fpl, self.acft)



selection = Selection()









##------------------------------------##
##                                    ##
##            USEFUL TOOLS            ##
##                                    ##
##------------------------------------##


class Ticker(QTimer):
	def __init__(self, action_callback, parent=None):
		'''
		start can be overridden with a timedelta or numeric milliseconds
		'''
		QTimer.__init__(self, parent)
		self.do_action = action_callback
		self.timeout.connect(self.do_action)
	
	def start_stopOnZero(self, t, immediate=True):
		t = int(1000 * t.total_seconds() if isinstance(t, timedelta) else t)
		if t == 0:
			self.stop()
		else:
			if immediate:
				self.do_action()
			self.start(t)



