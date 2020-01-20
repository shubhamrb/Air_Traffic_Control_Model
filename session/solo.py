
from random import random, randint, choice, uniform
from datetime import timedelta
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer

from data.util import some, pop_all, bounded
from data.comms import ChatMessage, CpdlcMessage
from data.conflict import ground_separated
from data.db import known_aircraft_types, known_airline_codes, touch_down_speed, cruise_speed, wake_turb_cat, acft_cat
from data.fpl import FPL
from data.utc import now
from data.nav import Navpoint, world_navpoint_db, world_routing_db
from data.strip import Strip, received_from_detail, parsed_route_detail, assigned_SQ_detail, assigned_altitude_detail
from data.params import Heading, StdPressureAlt, Speed, distance_flown, time_to_fly
from data.instruction import Instruction
from data.weather import mkWeather

from session.env import env
from session.config import settings, XpdrAssignmentRange
from session.manager import SessionManager, SessionType, CallsignGenerationError, HandoverBlocked, CpdlcAuthorityTransferFailed

from ext.fgfs import send_packet_to_views, FGFS_model_liveries
from ext.tts import speech_synthesis_available, SpeechSynthesiser, speech_str2txt
from ext.sr import speech_recognition_available, InstructionRecogniser, radio_callsign_match, write_radio_callsign

from ai.controlled import ControlledAircraft, GS_alt
from ai.uncontrolled import UncontrolledAircraft
from ai.status import Status, SoloParams

from gui.misc import signals, selection, Ticker
from gui.actions import transfer_selected_or_instruct
from gui.dialog.settings import SemiCircRule


# ---------- Constants ----------

solo_ticker_interval = 50 # ms

exit_point_tolerance = 10 # NM
TTF_separation = timedelta(minutes=2)
max_attempts_for_aircraft_spawn = 5

XPDR_range_IFR_DEP = XpdrAssignmentRange('Auto-generated IFR DEP', 0o2101, 0o2177, None)
XPDR_range_IFR_ARR = XpdrAssignmentRange('Auto-generated IFR ARR', 0o3421, 0o3477, None)
XPDR_range_IFR_transit = XpdrAssignmentRange('Auto-generated IFR transit', 0o3001, 0o3077, None)

# -------------------------------


class SoloSessionManager(SessionManager):
	'''
	VIRTUAL!
	Subclass and define methods:
	- generateAircraftAndStrip(): return (ACFT, Strip) pair of possibly None values
	- handoverGuard(cs, atc): return str error msg if handover not OK
	'''
	def __init__(self, gui):
		SessionManager.__init__(self, gui)
		self.session_type = SessionType.SOLO
		self.session_ticker = Ticker(self.tickSessionOnce, parent=gui)
		self.weather_ticker = Ticker(self.setNewWeather, parent=gui)
		self.spawn_timer = QTimer(gui)
		self.spawn_timer.setSingleShot(True)
		self.voice_instruction_recogniser = None
		self.speech_synthesiser = None
		self.msg_is_from_session_manager = False # set to True before sending to avoid chat msg being rejected
		if speech_recognition_available:
			try:
				self.voice_instruction_recogniser = InstructionRecogniser(gui)
			except RuntimeError as err:
				settings.solo_voice_instructions = False
				QMessageBox.critical(self.gui, 'Sphinx error', \
					'Error setting up the speech recogniser (check log): %s\nVoice instructions disabled.' % err)
		if speech_synthesis_available:
			try:
				self.speech_synthesiser = SpeechSynthesiser(gui)
			except Exception as err:
				settings.solo_voice_readback = False
				QMessageBox.critical(self.gui, 'Pyttsx error', \
					'Error setting up the speech synthesiser: %s\nPilot read-back disabled.' % err)
		self.controlled_traffic = []
		self.uncontrolled_traffic = []
		self.current_local_weather = None
		self.simulation_paused_at = None # start time if session is paused; None otherwise
		self.spawn_timer.timeout.connect(lambda: self.spawnNewControlledAircraft(isSessionStart=False))
		self.playable_aircraft_types = settings.solo_aircraft_types[:]
		self.uncontrolled_aircraft_types = [t for t in known_aircraft_types() if cruise_speed(t) != None]
		pop_all(self.playable_aircraft_types, lambda t: t not in known_aircraft_types())
		pop_all(self.playable_aircraft_types, lambda t: cruise_speed(t) == None)
	
	def start(self, traffic_count):
		if self.playable_aircraft_types == []:
			QMessageBox.critical(self.gui, 'Not enough ACFT types', 'Cannot start simulation: not enough playable aircraft types.')
			env.ATCs.clear()
			return
		if self.voice_instruction_recogniser != None:
			self.voice_instruction_recogniser.startup()
			signals.kbdPTT.connect(self.voicePTT)
		if self.speech_synthesiser != None:
			self.speech_synthesiser.startup()
			signals.voiceMsg.connect(self.speech_synthesiser.radioMsg)
		self.controlled_traffic.clear()
		self.uncontrolled_traffic.clear()
		for i in range(traffic_count):
			self.spawnNewControlledAircraft(isSessionStart=True)
		self.adjustDistractorCount()
		self.simulation_paused_at = None
		self.setNewWeather()
		self.session_ticker.start_stopOnZero(solo_ticker_interval)
		self.startWeatherTicker()
		signals.voiceMsgRecognised.connect(self.handleVoiceInstrMessage)
		signals.soloSessionSettingsChanged.connect(self.startWeatherTicker)
		signals.soloSessionSettingsChanged.connect(self.adjustDistractorCount)
		signals.sessionStarted.emit()
		print('Solo simulation begins.')
	
	def stop(self):
		if self.isRunning():
			signals.voiceMsgRecognised.disconnect(self.handleVoiceInstrMessage)
			signals.soloSessionSettingsChanged.disconnect(self.startWeatherTicker)
			signals.soloSessionSettingsChanged.disconnect(self.adjustDistractorCount)
			if self.voice_instruction_recogniser != None:
				signals.kbdPTT.disconnect(self.voicePTT)
				self.voice_instruction_recogniser.shutdown()
				self.voice_instruction_recogniser.wait()
			if self.speech_synthesiser != None:
				signals.voiceMsg.disconnect(self.speech_synthesiser.radioMsg)
				self.speech_synthesiser.shutdown()
				self.speech_synthesiser.wait()
			self.spawn_timer.stop()
			self.weather_ticker.stop()
			self.simulation_paused_at = None
			self.session_ticker.stop()
			self.controlled_traffic.clear()
			self.uncontrolled_traffic.clear()
			signals.sessionEnded.emit()
	
	def isRunning(self):
		return self.session_ticker.isActive() or self.simulation_paused_at != None
	
	def myCallsign(self):
		return settings.location_code
	
	def getAircraft(self):
		return self.controlled_traffic + self.uncontrolled_traffic
	
	def pauseSession(self):
		if self.isRunning() and self.simulation_paused_at == None:
			self.simulation_paused_at = now()
			self.session_ticker.stop()
			signals.sessionPaused.emit()
	
	def resumeSession(self):
		if self.isRunning() and self.simulation_paused_at != None:
			pause_delay = now() - self.simulation_paused_at
			for acft in self.getAircraft():
				acft.moveHistoryTimesForward(pause_delay)
			self.session_ticker.start_stopOnZero(solo_ticker_interval)
			self.simulation_paused_at = None
			signals.sessionResumed.emit()
	
	
	## WEATHER
	
	def getWeather(self, station):
		return self.current_local_weather if station == settings.primary_METAR_station else None
	
	def setNewWeather(self):
		wind_info = None if self.current_local_weather == None else self.current_local_weather.mainWind()
		if wind_info == None:
			w1 = 10 * randint(1, 36)
			w2 = randint(5, 20)
			if env.airport_data != None and \
					not any(rwy.inUse() and abs(w1 - rwy.orientation().trueAngle()) <= 90 for rwy in env.airport_data.allRunways()):
				w1 += 180
		else:
			whdg, wspd, gusts, unit = wind_info
			w1 = whdg.trueAngle() + 10 * randint(-1, 1)
			w2 = bounded(5, wspd + randint(-4, 4), 20)
		windstr = '%03d%02dKT' % ((w1 - 1) % 360 + 1, w2)
		self.current_local_weather = mkWeather(settings.primary_METAR_station, wind=windstr)
		signals.newWeather.emit(settings.primary_METAR_station, self.current_local_weather)
	
	def startWeatherTicker(self):
		self.weather_ticker.start_stopOnZero(settings.solo_weather_change_interval, immediate=False)
	
	
	## COMMUNICATIONS
	
	def postRadioChatMsg(self, msg):
		if self.msg_is_from_session_manager:
			self.msg_is_from_session_manager = False
		else:
			raise ValueError('Text messages not supported in solo sessions.')
	
	def postAtcChatMsg(self, msg):
		raise ValueError('ATC chat not available in solo sessions.')
	
	
	## TICKING AND SPAWNING
	
	def controlledAcftNeeded(self):
		return len(self.controlled_traffic) < settings.solo_max_aircraft_count
	
	def killAircraft(self, acft):
		if env.cpdlc.isConnected(acft.identifier):
			env.cpdlc.endDataLink(acft.identifier)
		if len(pop_all(self.controlled_traffic, lambda a: a is acft)) == 0:
			pop_all(self.uncontrolled_traffic, lambda a: a is acft)
		signals.aircraftKilled.emit(acft)
	
	def adjustDistractorCount(self):
		while len(self.uncontrolled_traffic) > settings.solo_distracting_traffic_count: # too many uncontrolled ACFT
			self.killAircraft(self.uncontrolled_traffic[0])
		for i in range(settings.solo_distracting_traffic_count - len(self.uncontrolled_traffic)): # uncontrolled ACFT needed
			self.spawnNewUncontrolledAircraft()
	
	def spawnNewUncontrolledAircraft(self):
		rndpos = env.radarPos().moved(Heading(randint(1, 360), True), uniform(10, .8 * settings.radar_range))
		rndalt = StdPressureAlt(randint(1, 10) * 1000)
		if self.airbornePositionFullySeparated(rndpos, rndalt):
			acft_type = choice(self.uncontrolled_aircraft_types)
			params = SoloParams(Status(Status.AIRBORNE), rndpos, rndalt, Heading(randint(1, 360), True), cruise_speed(acft_type))
			params.XPDR_code = settings.uncontrolled_VFR_XPDR_code
			new_acft = self.mkAiAcft(acft_type, params, goal=None)
			if new_acft != None:
				self.uncontrolled_traffic.append(new_acft)
	
	def spawnNewControlledAircraft(self, isSessionStart=False):
		new_acft = None
		attempts = 0
		while new_acft == None and attempts < max_attempts_for_aircraft_spawn:
			new_acft, strip = self.generateAircraftAndStrip()
			attempts += 1
		if new_acft != None and self.controlledAcftNeeded() and self.simulation_paused_at == None:
			self.controlled_traffic.append(new_acft)
			if settings.controller_pilot_data_link and random() <= settings.solo_CPDLC_balance:
				env.cpdlc.beginDataLink(new_acft.identifier, self.myCallsign(), transferFrom=strip.lookup(received_from_detail))
			if strip != None:
				if isSessionStart:
					strip.linkAircraft(new_acft)
					strip.writeDetail(received_from_detail, None)
				signals.receiveStrip.emit(strip)
			if not env.cpdlc.isConnected(new_acft.identifier):
				new_acft.makeInitialContact(None if settings.location_radio_name == '' else settings.location_radio_name)
	
	def airbornePositionFullySeparated(self, pos, alt):
		try:
			horiz_near = [acft for acft in self.getAircraft() if acft.params.position.distanceTo(pos) < settings.horizontal_separation]
			ignore = next(acft for acft in horiz_near if abs(acft.params.altitude.diff(alt)) < settings.vertical_separation)
			return False
		except StopIteration: # No aircraft too close
			return True
	
	def groundPositionFullySeparated(self, pos, t):
		return all(ground_separated(acft, pos, t) for acft in self.getAircraft() if acft.isGroundStatus())
	
	def tickSessionOnce(self):
		if self.controlledAcftNeeded() and not self.spawn_timer.isActive():
			delay = randint(int(settings.solo_min_spawn_delay.total_seconds()), int(settings.solo_max_spawn_delay.total_seconds()))
			self.spawn_timer.start(1000 * delay)
		self.adjustDistractorCount()
		pop_all(self.controlled_traffic, lambda a: a.released or not env.pointInRadarRange(a.params.position))
		pop_all(self.uncontrolled_traffic, lambda a: a.ticks_to_live == 0)
		for acft in self.getAircraft():
			acft.tickOnce()
			send_packet_to_views(acft.fgmsLivePositionPacket())
	
	def mkAiAcft(self, acft_type, params, goal):
		'''
		goal=None for UncontrolledAircraft; otherwise ControlledAircraft
		returns None if something prevented fresh ACFT creation, e.g. CallsignGenerationError.
		'''
		params.XPDR_mode = 'S' if acft_cat(acft_type) in ['jets', 'heavy'] else 'C'
		airlines = known_airline_codes()
		if env.airport_data != None: # might be rendering in tower view, prefer ACFT with known liveries
			liveries_for_acft = FGFS_model_liveries.get(acft_type, {})
			if len(liveries_for_acft) > 0 and settings.solo_restrict_to_available_liveries:
				pop_all(airlines, lambda al: al not in liveries_for_acft)
		try:
			callsign = self.generateCallsign(acft_type, airlines)
			if goal == None:
				ms_to_live = 1000 * 60 * randint(10, 60 * 3)
				return UncontrolledAircraft(callsign, acft_type, params, ms_to_live // solo_ticker_interval)
			else:
				return ControlledAircraft(callsign, acft_type, params, goal)
		except CallsignGenerationError:
			return None
	
	
	## DEALING WITH INSTRUCTIONS
	
	def sendCpdlcMsg(self, callsign, msg):
		link = env.cpdlc.currentDataLink(callsign)
		if link != None:
			link.appendMessage(msg)
			if msg.type() == CpdlcMessage.INSTR: # other message types ignored (unimplemented in solo)
				try:
					acft = next(a for a in self.controlled_traffic if a.identifier == callsign) # uncontrolled traffic is not in contact
					acft.instruct([Instruction.fromEncodedStr(msg.contents())])
					# FUTURE ingest before instruct to allow exception raised or (delayed?) WILCO msg before actually executing
				except StopIteration: # ACFT not found or not connected
					print('WARNING: Aircraft %s not found.' % callsign)
				except Instruction.Error as err: # raised by ControlledAircraft.instruct
					link.appendMessage(CpdlcMessage(False, CpdlcMessage.REJECT, contents=str(err)))
				else: # instruction sent and already accepted
					link.appendMessage(CpdlcMessage(False, CpdlcMessage.ACK))
	
	def transferCpdlcAuthority(self, acft_callsign, atc_callsign):
		try:
			acft = next(a for a in self.controlled_traffic if a.identifier == acft_callsign)
			guard = self.handoverGuard(acft, atc_callsign)
			if guard == None:
				env.cpdlc.endDataLink(acft_callsign, transferTo=atc_callsign)
				acft.released = True
			else:
				raise CpdlcAuthorityTransferFailed(acft_callsign, atc_callsign, guard)
		except StopIteration:
			pass
	
	def disconnectCpdlc(self, callsign):
		env.cpdlc.endDataLink(callsign)
	
	def instrExpectedByVoice(self, itype):
		return settings.solo_voice_instructions \
			and itype in [Instruction.VECTOR_HDG, Instruction.VECTOR_ALT, Instruction.VECTOR_SPD, Instruction.HAND_OVER]
	
	def voicePTT(self, key, toggle):
		if self.voice_instruction_recogniser != None and settings.solo_voice_instructions and self.simulation_paused_at == None:
			if toggle:
				self.voice_instruction_recogniser.keyIn()
			else:
				self.voice_instruction_recogniser.keyOut()
	
	def rejectInstruction(self, msg):
		if settings.solo_erroneous_instruction_warning:
			QMessageBox.warning(self.gui, 'Erroneous/rejected instruction', msg)
	
	def instructAircraftByCallsign(self, callsign, instr):
		if not self.instrExpectedByVoice(instr.type):
			self._instructSequence([instr], callsign)
	
	def _instructSequence(self, instructions, callsign):
		try:
			acft = next(a for a in self.controlled_traffic if a.identifier == callsign) # uncontrolled traffic is not in contact
			self.msg_is_from_session_manager = True
			signals.chatInstructionSuggestion.emit(callsign, _instr_str(instructions, acft), True)
			try:
				acft.instruct(instructions)
				acft.readBack(instructions)
				if settings.solo_wilco_beeps:
					signals.wilco.emit()
			except Instruction.Error as err:
				acft.say('Unable. %s' % err, True)
				self.rejectInstruction('%s: "%s"' % (callsign, speech_str2txt(str(err))))
		except StopIteration:
			self.msg_is_from_session_manager = True
			signals.chatInstructionSuggestion.emit(callsign, _instr_str(instructions, None), True)
			self.rejectInstruction('Nobody answering callsign %s' % callsign)
	
	def handleVoiceInstrMessage(self, radio_callsign_tokens, instructions):
		acft_matches = [acft for acft in self.getAircraft() if radio_callsign_match(radio_callsign_tokens, acft.identifier)]
		if acft_matches == []:
			callsign_to_instruct = write_radio_callsign(radio_callsign_tokens)
		elif len(acft_matches) == 1:
			callsign_to_instruct = acft_matches[0].identifier
		else:
			acft_matches[0].say('Sorry, was this for me?', True)
			self.rejectInstruction('Used callsign matches several: %s' % ', '.join(acft.identifier for acft in acft_matches))
			return
		if len(acft_matches) == 1:
			for instr in instructions:
				if instr.type == Instruction.HAND_OVER:
					guard = self.handoverGuard(acft_matches[0], instr.arg[0])
					if guard != None:
						acft_matches[0].say('Negative. Staying with you.', True)
						self.rejectInstruction('Bad/untimely handover:\n%s' % guard)
						return
		self._instructSequence(instructions, callsign_to_instruct)
	
	def stripDroppedOnATC(self, strip, atc):
		if not self.instrExpectedByVoice(Instruction.HAND_OVER):
			cs = strip.callsign(acft=True)
			try:
				acft = next(a for a in self.controlled_traffic if a.identifier == cs)
				guard = self.handoverGuard(acft, atc)
				if guard == None:
					transfer_selected_or_instruct(atc)
				else:
					raise HandoverBlocked(guard)
			except StopIteration:
				return








# -----------------------------------------------------------------

def _instr_str(instructions, acft): # NOTE: function assumes voice and mouse instructions are NOT mixed in list
	if settings.solo_voice_instructions:
		prefix = '[V] ' if any(instr.isVoiceRecognised() for instr in instructions) else '[M] '
	else:
		prefix = ''
	return prefix + ', '.join(instr.suggestTextChatInstruction(acft) for instr in instructions)



def rnd_rwy(choose_from, condition):
	'''
	Picks a runway from the first arg list (or any by wind if empty), satisfying the given condition.
	'''
	if choose_from == []: # Choose any from current wind
		w = env.primaryWeather()
		main_wind = w.mainWind() if w != None else None
		main_wind_hdg = main_wind[0] if main_wind != None else Heading(360, True)
		choose_from = [rwy for rwy in env.airport_data.allRunways() if abs(main_wind_hdg.diff(rwy.orientation())) <= 90]
	choose_from = [rwy for rwy in choose_from if condition(rwy)]
	return None if choose_from == [] else choice(choose_from)




def restrict_speed_under_ceiling(spd, alt, ceiling):
	if alt.diff(ceiling) <= 0:
		return Speed(min(spd.kt, 250))
	else:
		return spd
		


def local_ee_point_closest_to(ad, exit_wanted):
	if exit_wanted:
		lst = world_routing_db.exitsFrom(env.airport_data.navpoint)
	else: # entry point wanted
		lst = world_routing_db.entriesTo(env.airport_data.navpoint)
	if len(lst) == 0:
		return None
	else:
		return min((p for p, legspec in lst), key=(lambda p: ad.coordinates.distanceTo(p.coordinates)))


def choose_dep_dest_AD(is_arrival):
	if settings.solo_prefer_entry_exit_ADs:
		ads = None
		if is_arrival and len(world_routing_db.entriesTo(env.airport_data.navpoint)) > 0: # pick a departure AD with exit points
			ads = world_routing_db.airfieldsWithExitPoints()
		elif not is_arrival and len(world_routing_db.exitsFrom(env.airport_data.navpoint)) > 0: # pick a dest. AD with entry points
			ads = world_routing_db.airfieldsWithEntryPoints()
		if ads != None:
			try:
				return choice(list(ad for ad in ads if ad.code != env.airport_data.navpoint.code))
			except IndexError: # raised by random.choice on empty sequence
				pass # fall back on a random world airport
	return choice(world_navpoint_db.byType(Navpoint.AD))



def inTWRrange(params):
	return params.position.distanceTo(env.radarPos()) <= settings.solo_TWR_range_dist \
		and params.altitude.diff(StdPressureAlt.fromFL(settings.solo_TWR_ceiling_FL)) < 0
	











# -----------------------------------------------------------------


class SoloSessionManager_AD(SoloSessionManager):
	def __init__(self, gui):
		SoloSessionManager.__init__(self, gui)
	
	def start(self, traffic_count): # overrides (but calls) parent's
		self.parkable_aircraft_types = \
			[t for t in self.playable_aircraft_types if env.airport_data.ground_net.parkingPositions(acftType=t) != []]
		# Start errors (cancels start)
		if settings.solo_role_GND and self.parkable_aircraft_types == []:
			QMessageBox.critical(self.gui, 'Insufficient ground data', 'You cannot play solo GND with no parkable ACFT type.')
			return
		# Start warnings
		if (settings.solo_role_GND or settings.solo_role_TWR) and settings.radar_signal_floor_level > max(0, env.airport_data.field_elevation):
			QMessageBox.warning(self.gui, 'Radar visibility warning', 'You are playing solo TWR/GND with radar signal floor above surface.')
		if settings.solo_role_DEP and settings.solo_ARRvsDEP_balance == 0:
			QMessageBox.warning(self.gui, 'No departures warning', 'You are playing DEP with no departures set.')
		if settings.solo_role_APP and settings.solo_ARRvsDEP_balance == 1:
			QMessageBox.warning(self.gui, 'No arrivals warning', 'You are playing APP with no arrivals set.')
		# Set up ATC neighbours
		env.ATCs.updateATC('CTR', env.radarPos(), 'En-route control centre', None)
		if settings.solo_role_GND:
			env.ATCs.updateATC('Ramp', None, 'Apron/gate services', None)
		else:
			env.ATCs.updateATC('GND', None, 'Airport ground', None)
		if not settings.solo_role_TWR:
			env.ATCs.updateATC('TWR', None, 'Tower', None)
		if not settings.solo_role_APP:
			env.ATCs.updateATC('APP', None, 'Approach', None)
		if not settings.solo_role_DEP:
			env.ATCs.updateATC('DEP', None, 'Departure', None)
		SoloSessionManager.start(self, traffic_count)
	
	def handoverGuard(self, acft, next_atc):
		# Bad or untimely handovers
		if next_atc == 'Ramp':
			if acft.statusType() != Status.TAXIING:
				return 'Ramp only accepts taxiing aircraft.'
			if not acft.isInboundGoal():
				return 'This aircraft is outbound!'
			if not acft.canPark():
				return 'Bring aircraft close to parking position before handing over to ramp.'
		elif next_atc == 'GND':
			if acft.statusType() != Status.TAXIING:
				return 'Ground only accepts taxiing aircraft.'
		elif next_atc == 'TWR':
			if acft.isInboundGoal():
				if not inTWRrange(acft.params):
					return 'Not in TWR range.'
			else:
				if not acft.statusType() != Status.READY:
					return 'Aircraft has not reported ready for departure.'
		elif next_atc == 'APP':
			if not acft.isInboundGoal():
				return 'Why hand over to APP?!'
			elif inTWRrange(acft.params):
				return 'This aircraft is in TWR range.'
		elif next_atc == 'DEP':
			if acft.isInboundGoal():
				return 'DEP only controls departures!'
			elif inTWRrange(acft.params):
				return 'TWR must keep control of aircraft until they fly out of tower range.'
		elif next_atc == 'CTR':
			if acft.isInboundGoal():
				return 'This aircraft is inbound your airport.'
			if settings.solo_role_DEP:
				point, alt = acft.goal
				if point != None and acft.params.position.distanceTo(point.coordinates) > exit_point_tolerance:
					return 'Not close enough to exit point'
				if acft.params.altitude.diff(StdPressureAlt.fromFL(settings.solo_APP_ceiling_FL_min)) < 0:
					return 'Not high enough for CTR: reach FL%03d before handing over.' % settings.solo_APP_ceiling_FL_min
			else:
				return 'You should not be handing over to the centre directly.'
		else:
			print('INTERNAL ERROR: Please report unexpected ATC name "%s" in solo mode' % next_atc)
	
	
	def generateAircraftAndStrip(self):
		new_acft = received_from = None
		is_arrival = random() >= settings.solo_ARRvsDEP_balance
		if is_arrival:
			dep_ad = choose_dep_dest_AD(True)
			dest_ad = env.airport_data.navpoint
			midpoint = local_ee_point_closest_to(dest_ad, False) # None if none found
			if settings.solo_role_APP:
				new_acft = self.new_arrival_APP(midpoint)
				received_from = 'CTR'
			elif settings.solo_role_TWR:
				new_acft = self.new_arrival_TWR()
				received_from = 'APP'
			elif settings.solo_role_GND:
				new_acft = self.new_arrival_GND()
				received_from = 'TWR'
		else: # Create a departure
			dep_ad = env.airport_data.navpoint
			dest_ad = choose_dep_dest_AD(False)
			midpoint = local_ee_point_closest_to(dep_ad, True) # None if none found
			if settings.solo_role_GND:
				new_acft = self.new_departure_GND(midpoint)
				received_from = 'DEL'
			elif settings.solo_role_TWR:
				new_acft = self.new_departure_TWR(midpoint)
				received_from = 'GND'
			elif settings.solo_role_DEP:
				new_acft = self.new_departure_DEP(midpoint)
				received_from = 'TWR'
		if new_acft == None:
			return None, None
		else:
			strip = Strip()
			strip.writeDetail(FPL.CALLSIGN, new_acft.identifier)
			strip.writeDetail(FPL.ACFT_TYPE, new_acft.aircraft_type)
			strip.writeDetail(FPL.WTC, wake_turb_cat(new_acft.aircraft_type))
			strip.writeDetail(FPL.FLIGHT_RULES, 'IFR')
			strip.writeDetail(assigned_SQ_detail, new_acft.params.XPDR_code)
			strip.writeDetail(received_from_detail, received_from)
			if received_from == 'CTR':
				strip.writeDetail(assigned_altitude_detail, env.readStdAlt(new_acft.params.altitude))
			elif received_from == 'TWR' and not settings.solo_role_GND:
				strip.writeDetail(assigned_altitude_detail, settings.solo_initial_climb_reading)
			# routing details
			strip.writeDetail(FPL.ICAO_DEP, dep_ad.code)
			strip.writeDetail(FPL.ICAO_ARR, dest_ad.code)
			if is_arrival and midpoint != None: # arrival with local entry point
				try:
					strip.writeDetail(FPL.ROUTE, world_routing_db.shortestRouteStr(dep_ad, midpoint) + ' ' + midpoint.code)
				except ValueError:
					strip.writeDetail(FPL.ROUTE, 'DCT %s' % midpoint.code)
			elif not is_arrival and midpoint != None: # departure with local exit point
				try:
					strip.writeDetail(FPL.ROUTE, midpoint.code + ' ' + world_routing_db.shortestRouteStr(midpoint, dest_ad))
				except ValueError:
					strip.writeDetail(FPL.ROUTE, '%s DCT' % midpoint.code)
			return new_acft, strip
	
	
	## GENERATING DEPARTURES
	
	def new_departure_GND(self, goal_point):
		acft_type = choice(self.parkable_aircraft_types)
		gn = env.airport_data.ground_net
		pk = [p for p in gn.parkingPositions(acftType=acft_type) if self.groundPositionFullySeparated(gn.parkingPosition(p), acft_type)]
		if pk == []:
			return None
		pkinfo = env.airport_data.ground_net.parkingPosInfo(choice(pk))
		params = SoloParams(Status(Status.TAXIING), pkinfo[0], env.groundStdPressureAlt(pkinfo[0]), pkinfo[1], Speed(0))
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_DEP)
		return self.mkAiAcft(acft_type, params, (goal_point, None))

	def new_departure_TWR(self, goal_point):
		acft_type = choice(self.parkable_aircraft_types if self.parkable_aircraft_types != [] else self.playable_aircraft_types)
		rwy = rnd_rwy([rwy for rwy in env.airport_data.allRunways() if rwy.use_for_departures], lambda rwy: rwy.acceptsAcftType(acft_type))
		if rwy == None:
			return None
		hdg = rwy.orientation() + 60
		pos = rwy.threshold(dthr=True).moved(hdg.opposite(), .04) # FUTURE use turn-offs backwards when ground net present
		params = SoloParams(Status(Status.READY, arg=rwy.name), pos, env.groundStdPressureAlt(pos), hdg, Speed(0))
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_DEP)
		return self.mkAiAcft(acft_type, params, (goal_point, None))

	def new_departure_DEP(self, goal_point):
		acft_type = choice(self.parkable_aircraft_types if self.parkable_aircraft_types != [] else self.playable_aircraft_types)
		rwy = rnd_rwy([rwy for rwy in env.airport_data.allRunways() if rwy.use_for_departures], lambda rwy: rwy.acceptsAcftType(acft_type))
		if rwy == None:
			return None
		thr = rwy.threshold()
		hdg = rwy.orientation()
		pos = thr.moved(hdg, settings.solo_TWR_range_dist)
		try: # Check for separation
			horiz_dist = [pos.distanceTo(acft.params.position) for acft in self.controlled_traffic if acft.isOutboundGoal()]
			if time_to_fly(min(horiz_dist), cruise_speed(acft_type)) < TTF_separation:
				return None
		except ValueError:
			pass # No departures in the sky yet
		alt = GS_alt(env.elevation(thr), rwy.param_FPA, pos.distanceTo(thr))
		ias = restrict_speed_under_ceiling(cruise_speed(acft_type), alt, StdPressureAlt.fromFL(100))
		params = SoloParams(Status(Status.AIRBORNE), pos, alt, hdg, ias)
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_DEP)
		acft = self.mkAiAcft(acft_type, params, (goal_point, None))
		acft.instructions.append(Instruction(Instruction.VECTOR_ALT, arg=settings.solo_initial_climb_reading))
		return acft
	
	
	## GENERATING ARRIVALS
	
	def new_arrival_GND(self):
		acft_type = choice(self.parkable_aircraft_types)
		rwy = rnd_rwy([rwy for rwy in env.airport_data.allRunways() if rwy.use_for_arrivals], lambda rwy: rwy.acceptsAcftType(acft_type))
		if rwy == None:
			return None
		turn_off_lists = l1, l2, l3, l4 = env.airport_data.ground_net.runwayTurnOffs(rwy, minroll=(rwy.length(dthr=True) * 2 / 3))
		for lst in turn_off_lists:
			pop_all(lst, lambda t: not self.groundPositionFullySeparated(env.airport_data.ground_net.nodePosition(t[1]), acft_type))
		if all(lst == [] for lst in turn_off_lists):
			return None
		else:
			turn_off_choice = choice(l1) if l1 != [] else (l2 + l3)[0]
		pos = env.airport_data.ground_net.nodePosition(turn_off_choice[1])
		hdg = rwy.orientation() + turn_off_choice[3]
		params = SoloParams(Status(Status.TAXIING), pos, env.groundStdPressureAlt(pos), hdg, Speed(0))
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_ARR)
		pk_request = choice(env.airport_data.ground_net.parkingPositions(acftType=acft_type))
		return self.mkAiAcft(acft_type, params, pk_request)
	
	def new_arrival_TWR(self):
		acft_type = choice(self.parkable_aircraft_types if self.parkable_aircraft_types != [] else self.playable_aircraft_types)
		ils = random() >= settings.solo_ILSvsVisual_balance
		rwy_ok = lambda rwy: rwy.acceptsAcftType(acft_type) and (not ils or rwy.hasILS())
		rwy = rnd_rwy([rwy for rwy in env.airport_data.allRunways() if rwy.use_for_arrivals], rwy_ok)
		if rwy == None:
			return None
		dthr = rwy.threshold(dthr=True)
		try:
			furthest = max([dthr.distanceTo(acft.params.position) for acft in self.controlled_traffic if acft.isInboundGoal()])
			dist = max(furthest + uniform(1, 2) * distance_flown(TTF_separation, cruise_speed(acft_type)), settings.solo_TWR_range_dist)
		except ValueError:
			dist = settings.solo_TWR_range_dist / 2
		if dist > min(settings.solo_TWR_range_dist * 1.5, settings.radar_range - 10):
			return None # to protect from creating aircraft out of radar range
		status = Status(Status.LANDING, arg=rwy.name) if ils else Status(Status.AIRBORNE)
		hdg = rwy.appCourse()
		alt = GS_alt(env.elevation(dthr), rwy.param_FPA, max(2, dist if ils else dist - 2))
		params = SoloParams(status, env.radarPos().moved(hdg.opposite(), dist), alt, hdg, touch_down_speed(acft_type))
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_ARR)
		acft = self.mkAiAcft(acft_type, params, ils)
		acft.instructions.append(Instruction(Instruction.EXPECT_RWY, arg=rwy.name))
		if ils:
			acft.instructions.append(Instruction(Instruction.CLEARED_APP))
		return acft
	
	def new_arrival_APP(self, entry_point):
		type_choice = self.parkable_aircraft_types if self.parkable_aircraft_types != [] else self.playable_aircraft_types
		# must be landable too
		rwy_choice = [rwy for rwy in env.airport_data.allRunways() if rwy.use_for_arrivals]
		if rwy_choice == []:
			rwy_choice = env.airport_data.allRunways()
		pop_all(type_choice, lambda t: all(not rwy.acceptsAcftType(t) for rwy in rwy_choice))
		if type_choice == []:
			return None
		acft_type = choice(type_choice)
		ils = any(rwy.hasILS() for rwy in rwy_choice) and random() >= settings.solo_ILSvsVisual_balance
		if entry_point == None:
			hdg = Heading(randint(1, 360), True)
			pos = env.radarPos().moved(hdg.opposite(), uniform(.33 * settings.radar_range, .75 * settings.radar_range))
		else:
			pos = entry_point.coordinates
			hdg = pos.headingTo(env.radarPos())
		alt = StdPressureAlt.fromFL(10 * randint(settings.solo_APP_ceiling_FL_min // 10, settings.solo_APP_ceiling_FL_max // 10))
		if not self.airbornePositionFullySeparated(pos, alt):
			return None
		ias = restrict_speed_under_ceiling(cruise_speed(acft_type), alt, StdPressureAlt.fromFL(150)) # 5000-ft anticipation
		params = SoloParams(Status(Status.AIRBORNE), pos, alt, hdg, ias)
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_ARR)
		return self.mkAiAcft(acft_type, params, ils)











# -----------------------------------------------------------------



class SoloSessionManager_CTR(SoloSessionManager):
	def __init__(self, gui):
		SoloSessionManager.__init__(self, gui)
		pop_all(self.playable_aircraft_types, lambda t: acft_cat(t) not in ['jets', 'heavy'])
	
	def start(self, traffic_count): # overrides (but calls) parent's
		p = lambda d: env.radarPos().moved(Heading(d, True), 1.5 * settings.map_range)
		env.ATCs.updateATC('N', p(360), 'North', None)
		env.ATCs.updateATC('S', p(180), 'South', None)
		env.ATCs.updateATC('E', p(90), 'East', None)
		env.ATCs.updateATC('W', p(270), 'West', None)
		SoloSessionManager.start(self, traffic_count)

	def handoverGuard(self, acft, atc):
		if acft.coords().distanceTo(env.radarPos()) <= settings.solo_CTR_range_dist:
			return 'Aircraft is still in your airspace.'
		# Check if expected receiver
		dist_key_expected = lambda atc: env.ATCs.getATC(atc).position.distanceTo(acft.goal.coordinates)
		expected_receiver = min(env.ATCs.knownATCs(), key=dist_key_expected)
		if atc != expected_receiver:
			return 'Destination is %s; hand over to %s.' % (acft.goal, expected_receiver)
		# Check if closest ATC
		dist_key_closest = lambda atc: env.ATCs.getATC(atc).position.distanceTo(acft.params.position)
		if atc != min(env.ATCs.knownATCs(), key=dist_key_closest):
			return 'ACFT not near enough this neighbour\'s airspace.'

	
	def generateAircraftAndStrip(self):
		start_angle = uniform(0, 360)
		start_pos = env.radarPos().moved(Heading(start_angle, True), settings.solo_CTR_range_dist)
		end_pos = env.radarPos().moved(Heading(start_angle + 90 + uniform(1, 179), True), settings.solo_CTR_range_dist)
		transit_hdg = start_pos.headingTo(end_pos)
		dep_ad = world_navpoint_db.findClosest(env.radarPos().moved(transit_hdg.opposite(), \
				uniform(1.2 * settings.map_range, 5000)), types=[Navpoint.AD])
		dest_ad = world_navpoint_db.findClosest(env.radarPos().moved(transit_hdg, \
				uniform(1.2 * settings.map_range, 5000)), types=[Navpoint.AD])
		if env.pointOnMap(dep_ad.coordinates) or env.pointOnMap(dest_ad.coordinates):
			return None, None
		
		candidate_midpoints = [p for code in settings.solo_CTR_routing_points \
				for p in env.navpoints.findAll(code, types=[Navpoint.NDB, Navpoint.VOR, Navpoint.FIX]) \
				if start_pos.distanceTo(p.coordinates) < start_pos.distanceTo(end_pos)]
		midpoint = None if candidate_midpoints == [] else choice(candidate_midpoints)
		
		FLd10 = randint(settings.solo_CTR_floor_FL // 10, settings.solo_CTR_ceiling_FL // 10)
		if settings.solo_CTR_semi_circular_rule == SemiCircRule.E_W and (FLd10 % 2 == 0) != (transit_hdg.magneticAngle() >= 180) \
			or settings.solo_CTR_semi_circular_rule == SemiCircRule.N_S and (FLd10 % 2 == 1) != (90 <= transit_hdg.magneticAngle() < 270):
			FLd10 += 1
			if 10 * FLd10 > settings.solo_CTR_ceiling_FL:
				return None, None
		p_alt = StdPressureAlt.fromFL(10 * FLd10)
		if not self.airbornePositionFullySeparated(start_pos, p_alt):
			return None, None
		acft_type = choice(self.playable_aircraft_types)
		hdg = start_pos.headingTo(some(midpoint, dest_ad).coordinates)
		params = SoloParams(Status(Status.AIRBORNE), start_pos, p_alt, hdg, cruise_speed(acft_type))
		params.XPDR_code = env.nextSquawkCodeAssignment(XPDR_range_IFR_transit)
		new_acft = self.mkAiAcft(acft_type, params, dest_ad)
		dist_key = lambda atc: env.ATCs.getATC(atc).position.distanceTo(start_pos)
		received_from = min(env.ATCs.knownATCs(), key=dist_key)
		
		strip = Strip()
		strip.writeDetail(FPL.CALLSIGN, new_acft.identifier)
		strip.writeDetail(FPL.ACFT_TYPE, new_acft.aircraft_type)
		strip.writeDetail(FPL.WTC, wake_turb_cat(new_acft.aircraft_type))
		strip.writeDetail(FPL.FLIGHT_RULES, 'IFR')
		strip.writeDetail(FPL.ICAO_DEP, dep_ad.code)
		strip.writeDetail(FPL.ICAO_ARR, dest_ad.code)
		strip.writeDetail(FPL.CRUISE_ALT, env.readStdAlt(new_acft.params.altitude))
		strip.writeDetail(assigned_altitude_detail, strip.lookup(FPL.CRUISE_ALT))
		strip.writeDetail(assigned_SQ_detail, new_acft.params.XPDR_code)
		strip.writeDetail(received_from_detail, received_from)
		if midpoint != None:
			strip.insertRouteWaypoint(midpoint)
		
		new_acft.instructions.append(Instruction(Instruction.FOLLOW_ROUTE, arg=strip.lookup(parsed_route_detail).dup()))
		return new_acft, strip



