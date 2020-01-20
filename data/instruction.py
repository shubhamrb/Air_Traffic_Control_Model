from copy import copy

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.params import Heading, Speed
from data.comms import CommFrequency


# ---------- Constants ----------

# -------------------------------


#
# Instructions and arg types
#
# VECTOR_HDG: Heading
# VECTOR_ALT: str (alt/FL reading)
# VECTOR_SPD: Speed
# VECTOR_DCT: Navpoint/str
# CANCEL_VECTOR_SPD
# FOLLOW_ROUTE: Route
# HOLD: Navpoint/str (fix), bool (standard right turns)
# SQUAWK: int
# HAND_OVER: str (next ATC), CommFrequency/None
# CANCEL_APP
# LINE_UP
# INTERCEPT_NAV: Navpoint/str, Heading
# INTERCEPT_LOC
# EXPECT_RWY: str (RWY name)
# TAXI: list (ground net node sequence)
# HOLD_POSITION
# CLEARED_APP
# CLEARED_TKOF
# CLEARED_TO_LAND
# SAY_INTENTIONS
#


class Instruction:
	enum = \
		VECTOR_HDG, VECTOR_ALT, VECTOR_SPD, VECTOR_DCT, CANCEL_VECTOR_SPD, FOLLOW_ROUTE, \
		HOLD, SQUAWK, HAND_OVER, CANCEL_APP, LINE_UP, INTERCEPT_NAV, INTERCEPT_LOC, EXPECT_RWY, \
		TAXI, HOLD_POSITION, CLEARED_APP, CLEARED_TKOF, CLEARED_TO_LAND, SAY_INTENTIONS = range(20)
	
	def type2str(t):
		return {
				Instruction.VECTOR_HDG: 'VECTOR_HDG',
				Instruction.VECTOR_ALT: 'VECTOR_ALT',
				Instruction.VECTOR_SPD: 'VECTOR_SPD',
				Instruction.VECTOR_DCT: 'VECTOR_DCT',
				Instruction.CANCEL_VECTOR_SPD: 'CANCEL_VECTOR_SPD',
				Instruction.FOLLOW_ROUTE: 'FOLLOW_ROUTE',
				Instruction.HOLD: 'HOLD',
				Instruction.SQUAWK: 'SQUAWK',
				Instruction.HAND_OVER: 'HAND_OVER',
				Instruction.CANCEL_APP: 'CANCEL_APP',
				Instruction.LINE_UP: 'LINE_UP',
				Instruction.INTERCEPT_NAV: 'INTERCEPT_NAV',
				Instruction.INTERCEPT_LOC: 'INTERCEPT_LOC',
				Instruction.EXPECT_RWY: 'EXPECT_RWY',
				Instruction.TAXI: 'TAXI',
				Instruction.HOLD_POSITION: 'HOLD_POSITION',
				Instruction.CLEARED_APP: 'CLEARED_APP',
				Instruction.CLEARED_TKOF: 'CLEARED_TKOF',
				Instruction.CLEARED_TO_LAND: 'CLEARED_TO_LAND',
				Instruction.SAY_INTENTIONS: 'SAY_INTENTIONS'
			}[t]
	
	class Error(Exception):
		pass
	
	def __init__(self, init_type, arg=None, voiceData=None):
		'''
		When voice recognised: "voiceData" is a (possibly empty) str->str dict.
		'''
		self.type = init_type
		self.arg = arg
		self.voice_data = voiceData # currently known key: "rwy"
	
	def __str__(self):
		suffix = '' if self.arg == None else ':%s' % self.arg
		return 'I:%d%s' % (self.type, suffix)
	
	def dup(self):
		if self.type == Instruction.TAXI:
			return Instruction(Instruction.TAXI, arg=(self.arg[0][:], self.arg[1])) # The only needed manual deep copy
		else:
			return Instruction(self.type, arg=copy(self.arg))
	
	def isVoiceRecognised(self):
		return self.voice_data != None
	
	def suggestTextChatInstruction(self, acft):
		if self.type == Instruction.VECTOR_HDG:
			verb_str = 'Fly'
			if acft != None:
				hdg = acft.heading()
				if hdg != None:
					verb_str = 'Turn right' if hdg.diff(self.arg) < 0 else 'Turn left'
			return '%s heading %s' % (verb_str, self.arg.read())
		elif self.type == Instruction.VECTOR_ALT:
			verb_prefix = 'Fly'
			qnh_suffix = ''
			if acft != None:
				if acft.considerOnGround():
					verb_prefix = 'Initial climb' # Override
				else:
					c_alt = acft.xpdrAlt()
					if c_alt != None:
						try:
							v_alt = env.stdPressureAlt(self.arg)
						except ValueError:
							pass
						else:
							if c_alt.diff(v_alt) < 0:
								verb_prefix = 'Climb' # Override
							else:
								verb_prefix = 'Descend' # Override
								qnh = env.QNH(noneSafe=False)
								if qnh != None and v_alt.FL() < env.transitionLevel() <= c_alt.FL():
									qnh_suffix = ', QNH %d' % qnh # Override
			return '%s %s%s' % (verb_prefix, self.arg, qnh_suffix)
		elif self.type == Instruction.VECTOR_SPD:
			return 'Speed %s' % self.arg
		elif self.type == Instruction.VECTOR_DCT:
			return 'Proceed direct %s' % str(self.arg) # works for Navpoint and str types
		elif self.type == Instruction.CANCEL_VECTOR_SPD:
			return 'Speed your discretion'
		elif self.type == Instruction.FOLLOW_ROUTE:
			if acft == None:
				return 'Route %s' % self.arg
			else:
				legs_to_go = range(self.arg.currentLegIndex(acft.coords()), self.arg.legCount())
				return 'Proceed %s' % ' '.join(self.arg.legStr(i, start=False) for i in legs_to_go)
		elif self.type == Instruction.HOLD:
			fix, turns = self.arg
			return 'Hold at %s, %s turns' % (str(fix), ('right' if turns else 'left'))
		elif self.type == Instruction.SQUAWK:
			return 'Squawk %04o' % self.arg
		elif self.type == Instruction.CANCEL_APP:
			return 'Cancel approach, stand by for vectors'
		elif self.type == Instruction.HAND_OVER:
			return 'Contact %s%s, good bye.' % (self.arg[0], ('' if self.arg[1] == None else ' on %s' % self.arg[1]))
		elif self.type == Instruction.LINE_UP:
			if acft != None and settings.session_manager.session_type == SessionType.SOLO and acft.isReadyForDeparture():
				return 'Runway %s, line up and wait' % acft.params.status.arg
			else:
				return 'Line up and wait'
		elif self.type == Instruction.INTERCEPT_NAV:
			return 'Intercept %s from/to %s' % (self.arg[1].read(), str(self.arg[0]))
		elif self.type == Instruction.INTERCEPT_LOC:
			msg = 'Intercept localiser'
			if acft != None and settings.session_manager.session_type == SessionType.SOLO:
				instr = acft.instrOfType(Instruction.EXPECT_RWY)
				if instr != None:
					msg += ' for runway %s' % instr.arg
			return msg
		elif self.type == Instruction.EXPECT_RWY:
			return 'Expect runway %s' % self.arg
		elif self.type == Instruction.TAXI:
			if env.airport_data == None:
				return 'Taxi [???]'
			else:
				return env.airport_data.ground_net.taxiInstrStr(*self.arg)
		elif self.type == Instruction.HOLD_POSITION:
			return 'Hold position'
		elif self.type == Instruction.CLEARED_APP:
			if acft != None and settings.session_manager.session_type == SessionType.SOLO and acft.isInboundGoal() and not acft.wantsToPark():
				msg = 'Cleared for %s approach' % ('ILS' if acft.goal else 'visual')
				instr = acft.instrOfType(Instruction.EXPECT_RWY)
				if instr != None:
					msg += ' runway %s' % instr.arg
				return msg
			else:
				return 'Cleared for approach'
		elif self.type == Instruction.CLEARED_TKOF:
			if acft != None and settings.session_manager.session_type == SessionType.SOLO and acft.isReadyForDeparture():
				tkof_str = 'Runway %s, cleared for take-off' % acft.params.status.arg
			else:
				tkof_str = 'Cleared for take-off'
			w = env.primaryWeather()
			if w != None:
				tkof_str += ', wind %s' % w.readWind()
			return tkof_str
		elif self.type == Instruction.CLEARED_TO_LAND:
			rwy = None
			if acft != None and settings.session_manager.session_type == SessionType.SOLO:
				instr = acft.instrOfType(Instruction.EXPECT_RWY)
				if instr != None:
					rwy = instr.arg
			if rwy == None:
				ldg_str = 'Cleared to land'
			else:
				ldg_str = 'Runway %s, cleared to land' % rwy
			w = env.primaryWeather()
			if w != None:
				ldg_str += ', wind %s' % w.readWind()
			return ldg_str
		elif self.type == Instruction.SAY_INTENTIONS:
			return 'Say intentions?'
	
	
	## STRING ENCODING/DECODING
	
	def encodeToStr(self):
		tstr = Instruction.type2str(self.type)
		if self.type == Instruction.VECTOR_HDG:
			argstr = self.arg.read()
		elif self.type == Instruction.VECTOR_ALT:
			argstr = self.arg
		elif self.type == Instruction.VECTOR_SPD:
			argstr = '%03d' % self.arg.kt
		elif self.type == Instruction.HAND_OVER:
			argstr = self.arg[0]
			if self.arg[1] != None:
				argstr += ':%s' % self.arg[1]
		else:
			raise NotImplementedError('Instruction encoding for type %s' % tstr)
		return tstr if argstr == None else '%s %s' % (tstr, argstr)
	
	# Static
	def fromEncodedStr(txt):
		isplit = txt.split(maxsplit=1)
		try:
			instr_type = next(t for t in Instruction.enum if Instruction.type2str(t) == isplit[0])
			if instr_type == Instruction.VECTOR_HDG:
				return Instruction(instr_type, arg=Heading(int(isplit[1]), False))
			elif instr_type == Instruction.VECTOR_ALT:
				return Instruction(instr_type, arg=isplit[1])
			elif instr_type == Instruction.VECTOR_SPD:
				return Instruction(instr_type, arg=Speed(int(isplit[1])))
			elif instr_type == Instruction.HAND_OVER:
				fsplit = isplit[1].rsplit(':', maxsplit=1) # CAUTION assumes no ':' in callsign without freq suffix
				frq = None if len(fsplit) < 2 else CommFrequency(fsplit[1])
				return Instruction(instr_type, arg=(fsplit[0], frq))
		except (ValueError, IndexError, StopIteration):
			pass
		raise ValueError('Invalid/unrecognised instruction format')


