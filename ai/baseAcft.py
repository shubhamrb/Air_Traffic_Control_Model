
import re

from data.util import rounded
from data.acft import Aircraft, Xpdr
from data.params import StdPressureAlt
from data.utc import now
from data.db import known_airline_codes

from ai.status import Status

from session.config import settings
from session.env import env

from ext.fgfs import FGFS_model_and_height, FGFS_model_liveries
from ext.fgms import mkFgmsMsg_position, FGMS_prop_code_by_name, FGMS_prop_XPDR_capability, \
		FGMS_prop_XPDR_code, FGMS_prop_XPDR_ident, FGMS_prop_XPDR_alt, FGMS_prop_XPDR_gnd, FGMS_prop_XPDR_ias


# ---------- Constants ----------

RPM_low = 100
RPM_high = 1000
turn_roll_thr = 3 # degrees / s
right_turn_roll = 12 # degrees roll
pitch_factor = 30 / 3000 # degrees / (ft/min)
final_pitch = 2 # degrees
lift_off_pitch = 4 # 
runway_excursion_roll = 2 # degrees
runway_excursion_pitch = -3 # degrees
gear_compression_low = 0
gear_compression_high = .5

# commercial callsign regexp groups: 1=airline code; 2=flight number
commercial_callsign_regexp = re.compile('([0-9A-Z]{1,2}[A-Z])(\d{4})')

# -------------------------------


FGMS_prop_text_chat = FGMS_prop_code_by_name('sim/multiplay/chat')
FGMS_prop_livery_file = FGMS_prop_code_by_name('sim/model/livery/file')
FGMS_props_gear_position = [FGMS_prop_code_by_name('gear/gear[%d]/position-norm' % i) for i in range(5)]
FGMS_props_gear_compression = [FGMS_prop_code_by_name('gear/gear[%d]/compression-norm' % i) for i in range(5)]
FGMS_props_engine_RPM = [FGMS_prop_code_by_name('engines/engine[%d]/rpm' % i) for i in range(4)]






class AbstractAiAcft(Aircraft):
	'''
	This class represents an abstract class for an AI aircraft.
	Derived classes should reimplement (otherwise NotImplementedError raised):
	- doTick()
			will be called on every "tickOnce" (unless ACFT is frozen), after "self.tick_interval"
			is updated with a duration, and should perform the horizontal/vertical displacements, etc.
			of the past tick_interval duration
	- statusSnapshot()
	- fromStatusSnapshot(snapshot)
	'''
	
	def __init__(self, callsign, acft_type, init_params):
		Aircraft.__init__(self, callsign, acft_type, init_params.position, init_params.geometricAltitude())
		match = commercial_callsign_regexp.match(callsign)
		if match and match.group(1) in known_airline_codes():
			self.airline = match.group(1)
			try:
				self.livery = FGFS_model_liveries[acft_type][self.airline]
			except KeyError:
				self.livery = None
		else:
			self.airline = self.livery = None
		self.params = init_params
		self.mode_S_squats = True
		self.tick_interval = None
		self.hdg_tick_diff = 0
		self.alt_tick_diff = 0
		self.released = False
	
	def doTick(self):
		raise NotImplementedError('AbstractAiAcft.doTick')
	
	
	## GENERAL ACCESS METHODS
	
	def statusType(self):
		return self.params.status.type
	
	def isGroundStatus(self):
		return self.statusType() in [Status.TAXIING, Status.READY, Status.LINED_UP, Status.RWY_TKOF, Status.RWY_LDG]
	
	
	## TICKING
	
	def tickOnce(self):
		if not self.frozen:
			self.tick_interval = now() - self.lastLiveUpdateTime()
			hdg_before_tick = self.params.heading
			alt_before_tick = self.params.altitude
			self.doTick()
			self.hdg_tick_diff = self.params.heading.diff(hdg_before_tick)
			self.alt_tick_diff = self.params.altitude.diff(alt_before_tick)
		self.updateLiveStatus(self.params.position, self.params.geometricAltitude(), self.xpdrData())
	
	def xpdrGndBit(self):
		return self.params.XPDR_mode == 'S' and self.mode_S_squats and self.isGroundStatus()
	
	def xpdrData(self):
		res = {}
		if self.params.XPDR_mode != '0':
			res[Xpdr.CODE] = self.params.XPDR_code
			res[Xpdr.IDENT] = self.params.XPDR_idents
		if self.params.XPDR_mode not in '0A':
			res[Xpdr.ALT] = StdPressureAlt(rounded(self.params.altitude.ft1013(), step=(100 if self.params.XPDR_mode == 'C' else 10)))
		if self.params.XPDR_mode not in '0AC':
			res[Xpdr.IAS] = self.params.ias
			res[Xpdr.GND] = self.xpdrGndBit()
			res[Xpdr.CALLSIGN] = self.identifier
			res[Xpdr.ACFT] = self.aircraft_type
		return res
	
	
	## FGMS PACKET
	
	def fgmsLivePositionPacket(self):
		model, height = FGFS_model_and_height(self.aircraft_type)
		coords, amsl = self.live_position
		if self.statusType() in [Status.AIRBORNE, Status.HLDG] and self.hdg_tick_diff != 0:
			deg_roll = (1 if self.hdg_tick_diff > 0 else -1) * right_turn_roll
		elif self.params.RWY_excursion_stage != 0: # skidding off RWY
			deg_roll = runway_excursion_roll
		else:
			deg_roll = 0
		if self.statusType() == Status.LANDING:
			deg_pitch = final_pitch
		elif self.statusType() == Status.RWY_TKOF and self.params.ias.diff(self.nose_lift_off_speed()) > 0:
			deg_pitch = lift_off_pitch
		elif self.params.RWY_excursion_stage == 2: # crashed off RWY
			deg_pitch = runway_excursion_pitch
		elif self.isGroundStatus() or self.tick_interval == None: # tick interval None when started frozen (never ticked once)
			deg_pitch = 0
		else:
			deg_pitch = pitch_factor * self.alt_tick_diff * 60 / self.tick_interval.total_seconds()
		# Build property dictionary...
		pdct = { FGMS_prop_text_chat: '' }
		if self.livery != None:
			pdct[FGMS_prop_livery_file] = self.livery
		# XPDR prop's
		pdct[FGMS_prop_XPDR_capability] = 1 if self.params.XPDR_mode in '0AC' else 2
		if self.params.XPDR_mode != '0':
			pdct[FGMS_prop_XPDR_code] = int('%o' % self.params.XPDR_code, base=10)
			if self.params.XPDR_mode != 'A':
				pdct[FGMS_prop_XPDR_alt] = int(self.params.altitude.ft1013())
			if self.params.XPDR_mode == 'S':
				pdct[FGMS_prop_XPDR_gnd] = self.xpdrGndBit()
				pdct[FGMS_prop_XPDR_ias] = int(self.params.ias.kt)
			pdct[FGMS_prop_XPDR_ident] = self.params.XPDR_idents
		# engines
		for prop in FGMS_props_engine_RPM:
			pdct[prop] = RPM_low if self.isGroundStatus() and self.params.ias.kt < 1 else RPM_high
		# landing gear
		for prop in FGMS_props_gear_position: # FLOAT: 0=retracted; 1=extended
			pdct[prop] = float(self.isGroundStatus() or self.statusType() == Status.LANDING)
		for prop in FGMS_props_gear_compression: # FLOAT: 0=free; 1=compressed
			pdct[prop] = gear_compression_high if self.isGroundStatus() else gear_compression_low
		# finished
		return mkFgmsMsg_position(self.identifier, model, coords, amsl + height, \
				hdg=self.params.heading.trueAngle(), pitch=deg_pitch, roll=deg_roll, properties=pdct)
	
	
	## SNAPSHOTS
	
	def fromStatusSnapshot(snapshot):
		raise NotImplementedError('AbstractAiAcft.fromStatusSnapshot')
	
	def statusSnapshot(self):
		raise NotImplementedError('AbstractAiAcft.statusSnapshot')

