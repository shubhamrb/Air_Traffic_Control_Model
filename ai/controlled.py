from datetime import timedelta
from random import random, choice

from gui.misc import signals
from ext.tts import new_voice, speak_callsign_commercial_flight, speak_callsign_tail_number, speech_str2txt, speech_str2tts

from ai.status import Status
from ai.baseAcft import AbstractAiAcft

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.util import pop_all, some
from data.coords import EarthCoords
from data.conflict import ground_separated
from data.nav import Navpoint, Airfield, NavpointError
from data.comms import ChatMessage
from data.params import Speed, Heading, StdPressureAlt, distance_flown, wind_effect
from data.db import take_off_speed, touch_down_speed, stall_speed, maximum_speed, cruise_speed
from data.instruction import Instruction


# ---------- Constants ----------

pilot_turn_speed = 3 # degrees per second
pilot_vert_speed = 1800 # ft / min
pilot_accel = 3 # kt / s
pilot_hdg_precision = 2 # degrees
pilot_alt_precision = 20 # ft
pilot_spd_precision = 5 # kt
pilot_nav_precision = 1 # NM
pilot_taxi_precision = .002 # NM
pilot_sight_range = 7.5 # NM
pilot_sight_ceiling = StdPressureAlt.fromFL(100)

fast_turn_factor = 2.5
fast_climb_descend_factor = 1.75
fast_accel_decel_factor = 1.75

cockpit_IAS_reduction_floor = StdPressureAlt.fromFL(90)
cockpit_IAS_reduction_rate = .2

touch_down_distance_tolerance = .03 # NM
touch_down_height_tolerance = 50 # ft
touch_down_heading_tolerance = 5 # degrees
touch_down_speed_tolerance = 25 # kt
touch_down_speed_drop = 20 # kt
min_clearToLand_height = 50 # ft
lift_off_speed_factor = .9 # mult. stall speed
taxi_max_turn_without_decel = 5 # degrees
intercept_max_angle = 10 # degrees on each side

taxi_speed = Speed(15)
taxi_turn_speed = Speed(2)
ldg_roll_speed = Speed(25)
MISAP_climb_reading = '5000 ft'

short_final_dist = 4 # NM
inbound_speed_reduce_start_FL = 150
descent_max_speed = Speed(235)
default_turn_off_angle = -60 # degrees
turn_off_choice_prob = .5
approach_angle = 30 # degrees
init_hldg_turn = 120 # degrees
hldg_leg_fly_time = timedelta(minutes=1)
ready_max_dist_to_rwy = .05 # NM
park_max_dist_to_gate_node = .1 # NM

simulated_radio_signal_timeout = timedelta(seconds=2)

# -------------------------------



def ck_instr(accept_condition, msg_if_rejected):
	if not accept_condition:
		raise Instruction.Error(msg_if_rejected)


def GS_alt(thr_elev, fpa, dist):
	return StdPressureAlt.fromAMSL(thr_elev + 60.761 * fpa * dist, qnh=env.QNH())






class ControlledAircraft(AbstractAiAcft):
	'''
	This class represents an AI aircraft in radio contact (controlled),
	usually with intentions (goal) unless playing teacher.
	'''
	
	def __init__(self, callsign, acft_type, init_params, goal):
		'''
		goal parameter is:
		 - bool if and only if landing at base airport (True=ILS; False=visual)
		 - str if and only if requesting a parking position
		 - (Navpoint, cruise alt/lvl) if must be brought to a certain location/altitude (either can be None if don't matter)
		 - Airfield (destination) if it is transiting through airspace
		 - None if none of the above
		'''
		if cruise_speed(acft_type) == None:
			raise ValueError('Aborting ControlledAircraft construction: unknown cruise speed for %s' % acft_type)
		AbstractAiAcft.__init__(self, callsign, acft_type, init_params)
		self.pilot_voice = new_voice() if settings.session_manager.session_type == SessionType.SOLO else None
		self.goal = goal
		self.touch_and_go_on_LDG = False # set by teacher panel
		self.skid_off_RWY_on_LDG = False # set by teacher panel
		self.instructions = []
	
	
	## GENERAL ACCESS METHODS
	
	def pilotVoice(self):
		return self.pilot_voice
	
	def isInboundGoal(self):
		return isinstance(self.goal, bool) or isinstance(self.goal, str)
	
	def isOutboundGoal(self):
		return isinstance(self.goal, tuple)
	
	def wantsToPark(self):
		return isinstance(self.goal, str)
	
	def wantsVisualApp(self):
		return self.goal == False # (sic, self.goal not necessarily a bool)
	
	def wantsILS(self):
		return self.goal == True # (sic, self.goal not necessarily a bool)
	
	def canPark(self):
		if self.wantsToPark() and env.airport_data != None: # wants a gate/pkpos
			pkg_pos = env.airport_data.ground_net.parkingPosition(self.goal)
			return self.params.position.distanceTo(pkg_pos) <= park_max_dist_to_gate_node
		else:
			return False
	
	def isReadyForDeparture(self):
		return self.statusType() in [Status.READY, Status.LINED_UP]
	
	def instrOfType(self, t):
		'''
		returns the instruction of given type, or None
		'''
		return next((i for i in self.instructions if i.type == t), None)
	
	def groundPointInSight(self, point):
		return self.params.altitude.diff(pilot_sight_ceiling) <= 0 \
			and self.params.position.distanceTo(point) <= pilot_sight_range
	
	def maxTurn(self, timedelta):
		return pilot_turn_speed * timedelta.total_seconds()
	
	def maxClimb(self, timedelta):
		return pilot_vert_speed * timedelta.total_seconds() / 60
	
	def maxSpdIncr(self, timedelta):
		return pilot_accel * timedelta.total_seconds()
	
	def nose_lift_off_speed(self):
		return Speed(lift_off_speed_factor * stall_speed(self.aircraft_type).kt)
	
	
	
	## TICKING
	
	def doTick(self):
		#DEBUGprint(self.identifier, '(%s)' % self.params.status, ', '.join(str(i) for i in self.instructions))
		for instr in self.instructions:
			self.followInstruction(instr)
		if not self.isGroundStatus(): # control horiz. displacement
			if self.instrOfType(Instruction.VECTOR_SPD) == None: # see if we still want (or have) to change speed
				if self.params.ias.diff(Speed(250)) >= 0 and self.params.altitude.diff(StdPressureAlt.fromFL(100)) <= 0:
					self.accelDecelTowards(Speed(250), fast=True) # enforce speed restriction under FL100
				elif self.isInboundGoal():
					if self.statusType() != Status.LANDING: # landing status is covered by approachDescent method
						decel_for_descent = self.params.altitude.FL() <= inbound_speed_reduce_start_FL
						if not decel_for_descent:
							instr = self.instrOfType(Instruction.VECTOR_ALT)
							decel_for_descent = instr != None and env.stdPressureAlt(instr.arg).FL() <= inbound_speed_reduce_start_FL
						if decel_for_descent:
							self.accelDecelTowards(descent_max_speed, accelOK=False) # we may already be slower
				else:
					self.accelDecelTowards(cruise_speed(self.aircraft_type))
			if self.params.altitude.diff(cockpit_IAS_reduction_floor) < 0:
				eq_alt = self.params.altitude
			else: # reduce IAS-TAS diff. for less crazy speeds (IRL, IAS is set lower than cruise speed at high levels)
				eq_alt = cockpit_IAS_reduction_floor + cockpit_IAS_reduction_rate * self.params.altitude.diff(cockpit_IAS_reduction_floor)
			tas = self.params.ias.ias2tas(eq_alt)
			w = env.primaryWeather()
			wind_info = None if w == None else w.mainWind()
			if self.statusType() == Status.LANDING or wind_info == None or wind_info[0] == None:
				course = self.params.heading
				ground_speed = tas
			else: # WARNING: unit "kt" assumed for wind speed
				course, ground_speed = wind_effect(self.params.heading, tas, wind_info[0], Speed(wind_info[1]))
			self.params.position = self.params.position.moved(course, distance_flown(self.tick_interval, ground_speed))
		pop_all(self.instructions, self.instructionDone)
	
	
	# # # # # # # # # # # # #
	#     INSTRUCTIONS      #
	# # # # # # # # # # # # #
	
	## This is where the conditions are given for getting rid of instructions in ACFT instr. lists
	def instructionDone(self, instr):
		if instr.type in [Instruction.VECTOR_HDG, Instruction.VECTOR_ALT, Instruction.VECTOR_SPD, Instruction.FOLLOW_ROUTE]:
			return False
		elif instr.type == Instruction.VECTOR_DCT: # navpoint already resolved
			return self.params.position.distanceTo(instr.arg.coordinates) <= pilot_nav_precision
		elif instr.type == Instruction.CANCEL_VECTOR_SPD:
			return self.instrOfType(Instruction.VECTOR_SPD) == None
		elif instr.type == Instruction.HOLD:
			return False
		elif instr.type == Instruction.SQUAWK:
			return self.params.XPDR_code == instr.arg
		elif instr.type == Instruction.CANCEL_APP:
			return self.statusType() == Status.AIRBORNE and self.instrOfType(Instruction.CLEARED_TO_LAND) == None \
				and self.instrOfType(Instruction.CLEARED_APP) == None
		elif instr.type == Instruction.INTERCEPT_NAV:
			return False
		elif instr.type == Instruction.INTERCEPT_LOC:
			return self.instrOfType(Instruction.CLEARED_APP) != None
		elif instr.type == Instruction.EXPECT_RWY:
			return self.statusType() in [Status.RWY_LDG, Status.READY]
		elif instr.type == Instruction.TAXI:
			return instr.arg[0] == [] and instr.arg[1] == None
		elif instr.type == Instruction.HOLD_POSITION:
			return self.params.ias.diff(Speed(0)) == 0
		elif instr.type == Instruction.CLEARED_APP:
			return self.statusType() == Status.LANDING
		elif instr.type == Instruction.CLEARED_TO_LAND:
			return self.statusType() in [Status.TAXIING, Status.RWY_TKOF] # RWY cleared or performing touch-and-go
		elif instr.type == Instruction.LINE_UP:
			return self.statusType() == Status.LINED_UP
		elif instr.type == Instruction.CLEARED_TKOF:
			return self.statusType() == Status.AIRBORNE
		elif instr.type == Instruction.HAND_OVER:
			return self.released
		elif instr.type == Instruction.SAY_INTENTIONS: # This is followed in the read-back, so must be finished by now.
			return True
		else:
			assert False, 'instructionDone: unknown instruction %s' % instr
	
	## This is where instruction is given, possibly rejected by ACFT if makes no sense
	def instruct(self, instructions):
		'''
		given instructions might replace some in place, but ALWAYS end up in the list if no error is generated
		'''
		backup = self.instructions[:] # shallow copy is enough unless we start messing *inside* instructions in ingestInstruction
		try:
			for instr in instructions:
				self.ingestInstruction(instr) # this modifies self.instructions if the instr is not rejected
		except Instruction.Error as exn:
			self.instructions = backup
			raise exn
		else: # No instruction error raised; ADD instruction to list
			self.instructions.extend(instructions)
	
	## This is where AI pilot does something about an instruction of his list that he must follow
	def followInstruction(self, instr):
		if instr.type == Instruction.VECTOR_HDG:
			self.turnTowards(instr.arg, tolerance=pilot_hdg_precision)
			
		elif instr.type == Instruction.VECTOR_DCT:
			self.flyTowards(instr.arg.coordinates)
			if self.params.position.distanceTo(instr.arg.coordinates) <= pilot_nav_precision: # navpoint reached; do not circle
				self.instructions.append(Instruction(Instruction.VECTOR_HDG, arg=self.params.heading))
				# NOTE: current VECTOR_DCT instruction followed here will be removed at the end of this tick
			
		elif instr.type == Instruction.VECTOR_ALT:
			if not self.isGroundStatus():
				self.climbDescendTowards(env.stdPressureAlt(instr.arg))
			
		elif instr.type == Instruction.VECTOR_SPD:
			self.accelDecelTowards(instr.arg)
			
		elif instr.type == Instruction.FOLLOW_ROUTE:
			self.flyTowards(instr.arg.currentWaypoint(self.params.position).coordinates)
			
		elif instr.type == Instruction.CANCEL_VECTOR_SPD:
			pass # this instruction is immediately performed on "instruct"
		
		elif instr.type == Instruction.HOLD:
			hldg_fix, std_turns = instr.arg
			if self.statusType() != Status.HLDG:
				self.params.status = Status(Status.HLDG, arg=None)
			if self.params.status.arg == None: # going for fix
				if self.params.position.distanceTo(hldg_fix.coordinates) <= pilot_nav_precision: # got there
					hldg_hdg = self.params.heading + (init_hldg_turn if std_turns else -init_hldg_turn)
					self.params.status = Status(Status.HLDG, arg=(hldg_hdg, hldg_leg_fly_time))
				else:
					self.flyTowards(hldg_fix.coordinates)
			else: # in the loop
				hldg_hdg, outbound_ttf = self.params.status.arg
				if outbound_ttf > timedelta(0): # flying outbound leg
					if self.params.heading.diff(hldg_hdg, tolerance=pilot_hdg_precision) == 0:
						self.params.status.arg = hldg_hdg, self.params.status.arg[1] - self.tick_interval
					else:
						self.turnTowards(hldg_hdg, tolerance=pilot_hdg_precision)
				else: # flying inbound leg
					self.flyTowards(hldg_fix.coordinates)
					if self.params.position.distanceTo(hldg_fix.coordinates) <= pilot_nav_precision:
						self.params.status.arg = hldg_hdg, hldg_leg_fly_time
			
		elif instr.type == Instruction.SQUAWK:
			self.params.XPDR_code = instr.arg
			
		elif instr.type == Instruction.CANCEL_APP:
			self.MISAP()
				
		elif instr.type == Instruction.INTERCEPT_NAV:
			self.intercept(instr.arg[0].coordinates, instr.arg[1]) # FUTURE navaid intercept range limit?
				
		elif instr.type == Instruction.INTERCEPT_LOC:
			rwy = env.airport_data.runway(self.instrOfType(Instruction.EXPECT_RWY).arg)
			self.intercept(rwy.threshold(dthr=True), rwy.appCourse(), rangeLimit=rwy.LOC_range) # FUTURE limit to/from intercept
			
		elif instr.type == Instruction.EXPECT_RWY:
			rwy = env.airport_data.runway(instr.arg)
			if self.isGroundStatus():
				if self.instrOfType(Instruction.TAXI) == None and self.statusType() != Status.RWY_TKOF: # should we report ready?
					thr = rwy.threshold(dthr=False)
					rwy_limit = thr.moved(rwy.orientation(), rwy.length() / 2) # FUTURE roll-off dist depending on ACFT type
					if self.params.position.toRadarCoords().isBetween(thr.toRadarCoords(), rwy_limit.toRadarCoords(), ready_max_dist_to_rwy, offsetBeyondEnds=True):
						self.params.status = Status(Status.READY, arg=instr.arg)
						self.say('Short of \\RWY{%s}, ready for departure.' % rwy.name, False)
			else:
				td_point = rwy.threshold(dthr=True)
				if self.statusType() == Status.LANDING:
					self.intercept(td_point, rwy.appCourse(), tolerant=False, force=True)
					if self.instrOfType(Instruction.CANCEL_APP) == None:
						self.approachDescent(rwy)
				elif self.wantsVisualApp() and not self.params.runway_reported_in_sight and self.groundPointInSight(td_point):
					# Start visual approach
					self.say('Runway \\RWY{%s} in sight.' % rwy.name, False)
					self.params.runway_reported_in_sight = True
		
		elif instr.type == Instruction.TAXI:
			if self.statusType() != Status.RWY_LDG: # Other on-ground status with RWY argument
				self.params.status = Status(Status.TAXIING)
			if instr.arg[0] != []: # still got nodes to taxi
				next_target = env.airport_data.ground_net.nodePosition(instr.arg[0][0])
			elif instr.arg[1] != None: # final pkg pos
				next_target = env.airport_data.ground_net.parkingPosition(instr.arg[1])
			else: # no taxi goal left
				next_target = None
			if next_target != None:
				if self.taxiTowardsReached(next_target):
					if instr.arg[0] == []:
						instr.arg = [], None
					else: # still got nodes to taxi
						del instr.arg[0][0]
						if self.canPark() and instr.arg[0] == []:
							self.say('Request contact with ramp.', False)
			
		elif instr.type == Instruction.HOLD_POSITION:
			self.params.ias = Speed(0)
			
		elif instr.type == Instruction.CLEARED_APP:
			rwy = env.airport_data.runway(self.instrOfType(Instruction.EXPECT_RWY).arg)
			if self.params.runway_reported_in_sight \
					or self.intercept(rwy.threshold(dthr=True), rwy.appCourse(), tolerant=False, rangeLimit=rwy.LOC_range):
				pop_all(self.instructions, lambda i: i.type == Instruction.VECTOR_ALT)
				self.params.status = Status(Status.LANDING, arg=rwy.name)
			
		elif instr.type == Instruction.LINE_UP:
			if self.statusType() == Status.READY:
				rwy = env.airport_data.runway(self.params.status.arg)
				rwy_end = rwy.opposite().threshold(dthr=False)
				minimum_roll_dist = rwy.length() * 2 / 3 # FUTURE roll-off dist depending on ACFT type
				gn = env.airport_data.ground_net
				line_up_nodes = gn.nodes(lambda n: gn.nodeIsOnRunway(n, rwy.name) and gn.nodePosition(n).distanceTo(rwy_end) >= minimum_roll_dist)
				if line_up_nodes != []:
					# TODO instead of below: choose the one with shortest taxi route from closest node, or filter list above to only contain ORIGINAL nodes (not starting with 'ADDED:')
					line_up_point = min((gn.nodePosition(n) for n in line_up_nodes), key=self.params.position.distanceTo)
				if line_up_point == None: # none chosen yet
					rwy_dthr = rwy.threshold(dthr=True)
					rcoords_me = self.params.position.toRadarCoords()
					rcoords_dthr = rwy_dthr.toRadarCoords()
					rcoords_end = rwy_end.toRadarCoords()
					if rcoords_me.isBetween(rcoords_dthr, rcoords_end, ready_max_dist_to_rwy + 1, offsetBeyondEnds=False):
						line_up_point = EarthCoords.fromRadarCoords(rcoords_me.orthProj(rcoords_dthr, rcoords_end))
					else: # ACFT is behind the DTHR (not between RWY ends)
						line_up_point = rwy_dthr.moved(rwy.orientation(), .03)
				if self.taxiTowardsReached(line_up_point):
					hdg = rwy.orientation()
					if self.params.heading.diff(hdg, tolerance=.01) != 0:
						self.turnTowards(hdg, fastOK=True)
					else:
						pop_all(self.instructions, lambda i: i.type == Instruction.LINE_UP)
						self.params.status.type = Status.LINED_UP
			
		elif instr.type == Instruction.CLEARED_TKOF:
			if self.statusType() == Status.LINED_UP:
				self.params.status.type = Status.RWY_TKOF
			elif self.statusType() == Status.RWY_TKOF:
				self.taxiForward()
				self.params.ias += self.maxSpdIncr(self.tick_interval)
				if self.params.ias.diff(take_off_speed(self.aircraft_type)) >= 0:
					self.params.status = Status(Status.AIRBORNE)
					if self.instrOfType(Instruction.VECTOR_ALT) == None:
						self.instructions.append(Instruction(Instruction.VECTOR_ALT, arg=settings.solo_initial_climb_reading))
			
		elif instr.type == Instruction.CLEARED_TO_LAND and self.statusType() == Status.RWY_LDG and self.params.RWY_excursion_stage != 2:
			# 3 stages after touch down (stage 1 for all planes; then either skid off RWY or stages 2-3 for normal LDG):
			#   1. slow down (speed > ldg_roll_speed)
			#   2. LDG roll until turn-off point ahead if any (speed == ldg_roll_speed)
			#   3. turn/taxi off RWY (speed == taxi_speed)
			#      (3a) following taxi routes if possible (a TAXI instruction is present)
			#      (3b) "into the wild" if no ground net (no TAXI instruction present)
			if self.instrOfType(Instruction.TAXI) == None: # A taxi instruction (from a stage 3b) will take care of forward move
				self.taxiForward()
			rwy = env.airport_data.runway(self.params.status.arg)
			if self.params.ias.diff(ldg_roll_speed) > 0: # In stage 1
				self.accelDecelTowards(ldg_roll_speed, fast=True, tol=0)
			elif self.params.RWY_excursion_stage != 0:
				if self.params.RWY_excursion_stage == 1: # not finished
					finish_heading = rwy.orientation() + default_turn_off_angle
					self.turnTowards(finish_heading, fastOK=True)
					if self.params.heading.diff(finish_heading, tolerance=.1) == 0: # just finished skidding
						self.params.RWY_excursion_stage = 2
						self.say('Oops!', False)
			else:
				turning_off = False # init
				roll_dist = rwy.threshold().distanceTo(self.params.position)
				l1, l2, l3, l4 = env.airport_data.ground_net.runwayTurnOffs(rwy, minroll=roll_dist)
				fwd_turn_offs_available = l1 if l1 != [] else l2
				if self.instrOfType(Instruction.TAXI) != None: # In stage 3a
					turning_off = True
					into_the_wild = False
				elif fwd_turn_offs_available == []:
					if l3 == []: # No turn-off ahead + no possible backtrack. Going to stage (3b).
						turning_off = into_the_wild = True
					else: # Must stop, ACFT will need a backtrack
						self.accelDecelTowards(Speed(0), fast=(roll_dist > rwy.length(dthr=True) * 3 / 4), tol=0)
						if self.params.ias.diff(Speed(0)) == 0:
							self.params.status = Status(Status.TAXIING) # This finishes the instruction
							self.say('Requesting backtrack runway \\RWY{%s}' % rwy.name, False)
				else: # In stage 2
					next_turn_off_point = env.airport_data.ground_net.nodePosition(fwd_turn_offs_available[0][0])
					#DEBUGprint('Found node %s for turn off onto %s, distance %f' % (fwd_turn_offs_available[0][0], fwd_turn_offs_available[0][1], next_turn_off_point.distanceTo(env.airport_data.ground_net.nodePosition(fwd_turn_offs_available[0][1]))))
					if self.params.position.distanceTo(next_turn_off_point) < 2 * pilot_taxi_precision: # chance to turn off
						if len(fwd_turn_offs_available) == 1 or random() < turn_off_choice_prob: # turn off RWY! going to stage 3a
							self.instructions.append(Instruction(Instruction.TAXI, arg=([fwd_turn_offs_available[0][1]], None)))
				if turning_off: # In stage 3
					if into_the_wild:
						if self.params.ias.diff(taxi_speed) > .1: # slow down first
							self.accelDecelTowards(taxi_speed, fast=True, tol=0)
						else:
							finish_heading = rwy.orientation() + default_turn_off_angle
							self.turnTowards(finish_heading, fastOK=True)
							turning_off = self.params.heading.diff(finish_heading, tolerance=.1) != 0
					else:
						turning_off = self.instrOfType(Instruction.TAXI) == None # reached RWY cleared point
					if not turning_off: # turn-off finished
						self.params.ias = Speed(0)
						if settings.session_manager.session_type == SessionType.SOLO and settings.solo_role_GND:
							self.goal = choice(env.airport_data.ground_net.parkingPositions(acftType=self.aircraft_type))
							pkinfo = env.airport_data.ground_net.parkingPosInfo(self.goal)
							self.say('Runway \\RWY{%s} clear for %s \\SPELL_ALPHANUMS{%s}.' % (rwy.name, pkinfo[2], self.goal), False)
						else:
							self.say('Runway \\RWY{%s} clear.' % rwy.name, False)
						self.params.status = Status(Status.TAXIING) # This finishes the instruction
			
		elif instr.type == Instruction.SAY_INTENTIONS:
			pass # This is followed on read-back. Nothing to do at this point.
			
		elif instr.type == Instruction.HAND_OVER:
			if env.cpdlc.isConnected(self.identifier):
				env.cpdlc.endDataLink(self.identifier)
			self.released = True
	
	
	## INSTRUCTION CHECKING
	
	def ingestInstruction(self, instr):
		try:
			if instr.type == Instruction.VECTOR_DCT: # arg is single navpoint
				instr.arg = env.navpoints.findClosest(env.radarPos(), code=instr.arg)
			elif instr.type in [Instruction.HOLD, Instruction.INTERCEPT_NAV]: # arg is pair with navpoint first
				navpoint = env.navpoints.findClosest(env.radarPos(), code=instr.arg[0], types=[Navpoint.VOR, Navpoint.NDB])
				instr.arg = navpoint, instr.arg[1]
		except NavpointError as err:
			raise Instruction.Error('Cannot identify \\NAVPOINT{%s}??' % err)
		
		if instr.type in [Instruction.VECTOR_HDG, Instruction.VECTOR_DCT, Instruction.FOLLOW_ROUTE]:
			if instr.type == Instruction.VECTOR_DCT:
				ck_instr(self.params.position.distanceTo(instr.arg.coordinates) > pilot_nav_precision, 'Already at %s.' % instr.arg.code)
			ck_instr(self.instrOfType(Instruction.CLEARED_APP) == None, 'Already cleared for approach. Should I cancel clearance?')
			ck_instr(self.statusType() in [Status.AIRBORNE, Status.HLDG], 'Sorry, not a time for vectors.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.VECTOR_HDG, Instruction.VECTOR_DCT, \
					Instruction.INTERCEPT_NAV, Instruction.INTERCEPT_LOC, Instruction.FOLLOW_ROUTE, Instruction.HOLD])
			if self.statusType() == Status.HLDG:
				self.params.status = Status(Status.AIRBORNE)
			
		elif instr.type == Instruction.VECTOR_ALT:
			if self.isGroundStatus(): # instr = initial climb
				ck_instr(not self.isInboundGoal(), 'Not outbound.')
			else: # instr = climb/descend
				ck_instr(self.instrOfType(Instruction.CLEARED_APP) == None, 'Already cleared for approach. Should I cancel clearance?')
			pop_all(self.instructions, lambda i: i.type == Instruction.VECTOR_ALT)
			
		elif instr.type == Instruction.VECTOR_SPD:
			ck_instr(not self.isGroundStatus(), 'Not airborne.')
			if self.statusType() == Status.LANDING:
				ck_instr(self.params.position.distanceTo(env.airport_data.navpoint.coordinates) > short_final_dist, 'On short final.')
			ck_instr(instr.arg.diff(stall_speed(self.aircraft_type)) >= 0, 'Speed is too low.')
			ck_instr(instr.arg.diff(maximum_speed(self.aircraft_type)) <= 0, 'Cannot reach such speed.')
			pop_all(self.instructions, lambda i: i.type == Instruction.VECTOR_SPD)
			
		elif instr.type == Instruction.CANCEL_VECTOR_SPD:
			ck_instr(not self.isGroundStatus(), 'Not airborne.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.CANCEL_VECTOR_SPD, Instruction.VECTOR_SPD])
			
		elif instr.type == Instruction.INTERCEPT_NAV:
			ck_instr(self.statusType() == Status.AIRBORNE and self.instrOfType(Instruction.CLEARED_APP) == None, \
					'Sorry, not a time for vectors.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.INTERCEPT_NAV, Instruction.INTERCEPT_LOC])
			
		elif instr.type == Instruction.INTERCEPT_LOC:
			ck_instr(not self.isGroundStatus(), 'Not airborne!')
			ck_instr(self.statusType() != Status.LANDING, 'Already landing.')
			ck_instr(self.statusType() != Status.HLDG, 'Still on hold.')
			self.ckVoiceInstrAndEnsureRwy(instr)
			ck_instr(self.instrOfType(Instruction.CLEARED_APP) == None, 'Already cleared for approach. Should I cancel clearance?')
			ck_instr(not self.wantsVisualApp(), 'Requesting visual approach.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.INTERCEPT_NAV, Instruction.INTERCEPT_LOC])
			
		elif instr.type == Instruction.HOLD:
			ck_instr(self.statusType() in [Status.AIRBORNE, Status.HLDG], 'Sorry, not a time to hold.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.VECTOR_HDG, Instruction.VECTOR_DCT, \
					Instruction.INTERCEPT_NAV, Instruction.INTERCEPT_LOC, Instruction.FOLLOW_ROUTE, Instruction.HOLD])
			
		elif instr.type == Instruction.SQUAWK:
			pop_all(self.instructions, lambda i: i.type == Instruction.SQUAWK)
			
		elif instr.type == Instruction.CANCEL_APP:
			ck_instr(self.statusType() == Status.LANDING or self.instrOfType(Instruction.CLEARED_APP) != None, 'Not on approach.')
			pop_all(self.instructions, lambda i: i.type == Instruction.CANCEL_APP)
			
		elif instr.type == Instruction.LINE_UP:
			ck_instr(self.statusType() == Status.READY, 'Not ready.')
			if instr.isVoiceRecognised():
				str_voice_rwys = instr.voice_data['rwy']
				if str_voice_rwys != '':
					ck_instr(str_voice_rwys == self.params.status.arg, \
							'Ready for departure from \\RWY{%s}. Wrong runway?' % self.params.status.arg)
			pop_all(self.instructions, lambda i: i.type in [Instruction.LINE_UP, Instruction.CLEARED_TKOF])
			
		elif instr.type == Instruction.CLEARED_TKOF:
			ck_instr(self.statusType() in [Status.READY, Status.LINED_UP], 'Not waiting for departure.')
			if instr.isVoiceRecognised():
				str_voice_rwys = instr.voice_data['rwy']
				if str_voice_rwys != '':
					ck_instr(str_voice_rwys == self.params.status.arg, \
							'Ready for departure from \\RWY{%s}. Wrong runway?' % self.params.status.arg)
			if self.statusType() == Status.READY:
				self.instructions.append(Instruction(Instruction.LINE_UP, arg=self.params.status.arg))
			pop_all(self.instructions, lambda i: i.type == Instruction.CLEARED_TKOF)
			
		elif instr.type == Instruction.EXPECT_RWY:
			ck_instr(env.airport_data != None and instr.arg in env.airport_data.runwayNames(), 'Which runway??')
			if self.isGroundStatus():
				ck_instr(self.statusType() != Status.RWY_TKOF, 'Already taking off.')
				ck_instr(not self.isInboundGoal(), 'Not requesting departure.')
			else: # Not on ground
				ck_instr(not self.isOutboundGoal(), 'Outbound.')
				ck_instr(self.statusType() != Status.LANDING, 'Already landing.')
				ck_instr(self.instrOfType(Instruction.CLEARED_APP) == None, 'Already cleared for approach. Should I cancel clearance?')
				if instr.isVoiceRecognised(): # cannot be teacher mode
					app = instr.voice_data['app']
					ck_instr(app == None or app == self.wantsILS(), 'Requesting %s approach.' % self.ttsAppWanted())
				if self.wantsILS(): # RWY exists, requires ILS-capable
					ck_instr(env.airport_data.runway(instr.arg).hasILS(), 'Runway %s has no \\SPLIT_CHARS{ILS}.' % instr.arg)
			pop_all(self.instructions, lambda i: i.type in [Instruction.EXPECT_RWY, Instruction.INTERCEPT_LOC])
			self.params.runway_reported_in_sight = False
		
		elif instr.type == Instruction.TAXI:
			ck_instr(self.isGroundStatus(), 'Currently airborne!')
			ck_instr(self.statusType() != Status.RWY_TKOF, 'Already taking off.')
			pop_all(self.instructions, lambda i: i.type in [Instruction.TAXI, Instruction.HOLD_POSITION])
		
		elif instr.type == Instruction.HOLD_POSITION:
			ck_instr(self.statusType() != Status.RWY_TKOF, 'Already taking off.')
			ck_instr(self.statusType() in [Status.TAXIING, Status.READY, Status.LINED_UP], 'Not taxiing.')
			pop_all(self.instructions, lambda i: i.type in \
					[Instruction.HOLD_POSITION, Instruction.LINE_UP, Instruction.CLEARED_TKOF, Instruction.TAXI])
			
		elif instr.type == Instruction.CLEARED_APP:
			ck_instr(not self.isGroundStatus(), 'Not airborne!')
			ck_instr(self.statusType() != Status.LANDING, 'Already landing.')
			ck_instr(self.statusType() != Status.HLDG, 'Still on hold.')
			self.ckVoiceInstrAndEnsureRwy(instr)
			if settings.session_manager.session_type != SessionType.TEACHER:
				if instr.isVoiceRecognised():
					app = instr.voice_data['app']
					ck_instr(app == None or app == self.wantsILS(), 'Requesting %s approach.' % self.ttsAppWanted())
				ck_instr(not self.wantsVisualApp() or self.params.runway_reported_in_sight, 'Runway not in sight yet.')
			pop_all(self.instructions, lambda i: i.type == Instruction.CLEARED_APP)
			
		elif instr.type == Instruction.CLEARED_TO_LAND:
			ck_instr(settings.session_manager.session_type == SessionType.TEACHER or settings.solo_role_TWR, \
					'Only \\ATC{TWR} can issue this instruction.')
			ck_instr(self.statusType() == Status.LANDING, 'Not correctly on final.')
			got_expect_runway = self.instrOfType(Instruction.EXPECT_RWY)
			ck_instr(got_expect_runway != None, 'REPORT BUG! Landing without a runway :-(')
			if instr.isVoiceRecognised():
				voice_rwys = instr.voice_data['rwy']
				if voice_rwys != '':
					ck_instr(voice_rwys == got_expect_runway.arg, 'Established on final for \\RWY{%s}.' % got_expect_runway.arg)
			pop_all(self.instructions, lambda i: i.type == Instruction.CLEARED_TO_LAND)
			
		elif instr.type == Instruction.HAND_OVER:
			pop_all(self.instructions, lambda i: i.type == Instruction.HAND_OVER)
	
	def ckVoiceInstrAndEnsureRwy(self, instr):
		if instr.isVoiceRecognised():
			voice_rwys = instr.voice_data['rwy']
			if voice_rwys != '':
				expect_instr = self.instrOfType(Instruction.EXPECT_RWY)
				if expect_instr == None: # was not expecting a runway; is one included in this voice instruction?
					self.instruct([Instruction(Instruction.EXPECT_RWY, arg=voice_rwys)]) # if more than one listed here, name will be rejected
				else: # already expecting a runway; if one is included here, it should match
					ck_instr(voice_rwys == expect_instr.arg, 'Expecting runway \\RWY{%s}. Cancel this approach?' % expect_instr.arg)
		ck_instr(self.instrOfType(Instruction.EXPECT_RWY) != None, 'No runway given.')
	
	
	## AUXILIARY METHODS FOR INSTRUCTION FOLLOWING
	
	def intercept(self, point, hdg, tolerant=True, force=False, rangeLimit=None):
		dct = self.params.position.toRadarCoords().headingTo(point.toRadarCoords())
		opp = dct.opposite()
		interception = abs(hdg.diff(opp)) <= intercept_max_angle or abs(hdg.opposite().diff(opp)) <= intercept_max_angle # angle
		if rangeLimit != None:
			interception &= self.params.position.distanceTo(point) <= rangeLimit
		if interception or force: # in LOC/QDM/QDR cone
			pop_all(self.instructions, lambda i: i.type in [Instruction.VECTOR_HDG, Instruction.VECTOR_DCT, Instruction.FOLLOW_ROUTE])
			diff = dct.diff(hdg)
			delta = diff if abs(diff) < 90 else opp.diff(hdg)
			tol = pilot_hdg_precision if tolerant else 0
			self.turnTowards(hdg + delta * approach_angle / intercept_max_angle, tolerance=tol, fastOK=True)
		return interception
		
	def approachDescent(self, runway):
		touch_down_point = runway.threshold(dthr=True)
		touch_down_dist = self.params.position.distanceTo(touch_down_point)
		touch_down_elev = env.elevation(touch_down_point)
		# NOTE: Line above assumes XPDR in the wheels. OK for radar; live FGMS pos packet corrected if FGFS model height is known.
		gs_diff = self.params.altitude.diff(GS_alt(touch_down_elev, runway.param_FPA, touch_down_dist), tolerance=0)
		if gs_diff > 0: # must descend
			drop = min(fast_climb_descend_factor * self.maxClimb(self.tick_interval), gs_diff)
			self.params.altitude = self.params.altitude - drop
		on_short = touch_down_dist <= short_final_dist
		if on_short:
			pop_all(self.instructions, lambda i: i.type == Instruction.VECTOR_SPD)
		if self.instrOfType(Instruction.VECTOR_SPD) == None:
			self.accelDecelTowards(touch_down_speed(self.aircraft_type), fast=on_short)
		rwy_ori = runway.orientation()
		if abs(self.params.position.headingTo(touch_down_point).diff(rwy_ori)) >= 90:
			self.say('Facing wrong direction! Executing missed approach.', False)
			self.MISAP()
			return
		height = self.params.altitude.diff(env.groundStdPressureAlt(self.params.position))
		if not settings.teacher_ACFT_touch_down_without_clearance \
				and height < min_clearToLand_height and self.instrOfType(Instruction.CLEARED_TO_LAND) == None:
			self.say('Going around; not cleared to land.', False)
			self.MISAP()
		elif touch_down_dist <= touch_down_distance_tolerance: # Attempt touch down!
			alt_check = height <= touch_down_height_tolerance
			hdg_check = self.params.heading.diff(rwy_ori, tolerance=touch_down_heading_tolerance) == 0
			speed_check = self.params.ias.diff(touch_down_speed(self.aircraft_type), tolerance=touch_down_speed_tolerance) <= 0
			if alt_check and hdg_check and speed_check: # TOUCH DOWN!
				self.params.heading = rwy_ori
				self.params.ias -= touch_down_speed_drop
				if self.touch_and_go_on_LDG:
					self.params.status.type = Status.RWY_TKOF
					self.instructions.append(Instruction(Instruction.CLEARED_TKOF))
				else:
					self.params.status.type = Status.RWY_LDG
					if self.skid_off_RWY_on_LDG:
						self.params.RWY_excursion_stage = 1
			else: # Missed approach
				reason = ('not lined up' if speed_check else 'too fast') if alt_check else 'too high'
				self.say('Missed touch down: %s, going around.' % reason, False)
				self.MISAP()
	
	def taxiTowardsReached(self, target):
		dist = self.params.position.distanceTo(target)
		if dist <= pilot_taxi_precision: # target reached: stop
			self.params.ias = Speed(0)
			return True
		else: # must move
			hdg = self.params.position.headingTo(target)
			diff = self.params.heading.diff(hdg, tolerance=taxi_max_turn_without_decel)
			if diff == 0: # more or less facing goal
				self.params.heading = hdg
				self.params.ias = taxi_speed
			else: # must turn towards target point
				self.turnTowards(hdg, fastOK=True)
				self.params.ias = taxi_turn_speed
			self.taxiForward(maxdist=dist)
			return False # target not known to be reached yet
	
	def taxiForward(self, maxdist=None):
		dist = distance_flown(self.tick_interval, self.params.ias)
		if maxdist != None and dist > maxdist:
			dist = maxdist
		new_pos = self.params.position.moved(self.params.heading, dist)
		if self.statusType() not in [Status.TAXIING, Status.READY, Status.LINED_UP] \
			or all(ground_separated(other, new_pos, self.aircraft_type) \
				or new_pos.distanceTo(other.params.position) > self.params.position.distanceTo(other.params.position) \
				for other in settings.session_manager.getAircraft() if other is not self and other.isGroundStatus()):
			self.params.position = new_pos
			self.params.altitude = env.groundStdPressureAlt(self.params.position)
	
	def turnTowards(self, hdg, tolerance=0, fastOK=False):
		'''
		works airborne and on ground
		'''
		diff = hdg.diff(self.params.heading, tolerance)
		if diff != 0:
			max_abs_turn = (fast_turn_factor if fastOK else 1) * self.maxTurn(self.tick_interval)
			self.params.heading += (1 if diff > 0 else -1) * min(abs(diff), max_abs_turn)
	
	def flyTowards(self, coords):
		self.turnTowards(self.params.position.headingTo(coords), tolerance=pilot_hdg_precision)
	
	def climbDescendTowards(self, alt, climbOK=True, descendOK=True):
		diff = alt.diff(self.params.altitude, tolerance=pilot_alt_precision)
		if diff < 0 and descendOK or diff > 0 and climbOK:
			vert = min(self.maxClimb(self.tick_interval), abs(diff))
			self.params.altitude = self.params.altitude + (vert if diff > 0 else -vert)

	def accelDecelTowards(self, spd, accelOK=True, decelOK=True, fast=False, tol=pilot_spd_precision):
		diff = spd.diff(self.params.ias, tolerance=tol)
		if diff < 0 and decelOK or diff > 0 and accelOK:
			spdincr = min((fast_accel_decel_factor if fast else 1) * self.maxSpdIncr(self.tick_interval), abs(diff))
			self.params.ias = self.params.ias + (spdincr if diff > 0 else -spdincr)
	
	def MISAP(self):
		self.params.status = Status(Status.AIRBORNE)
		pop_all(self.instructions, lambda i: i.type in [Instruction.CLEARED_TO_LAND, Instruction.CLEARED_APP, Instruction.INTERCEPT_LOC])
		if self.params.altitude.diff(env.stdPressureAlt(MISAP_climb_reading)) < 0:
			self.instructions.append(Instruction(Instruction.VECTOR_ALT, arg=MISAP_climb_reading))
	
	
	## RADIO
	
	def say(self, txt_message, responding, initAddressee=None, cpdlc=None):
		'''
		responding: True if callsign should come last on the radio; False will place callsign first.
		initAddressee: msg starts with addressee callsign, followed by own without shortening.
		'''
		signals.incomingRadioChatMsg.emit(ChatMessage(self.identifier, speech_str2txt(txt_message)))
		if settings.session_manager.session_type == SessionType.SOLO:
			if settings.solo_voice_readback and self.pilotVoice() != None:
				if self.airline == None:
					cs = speak_callsign_tail_number(self.identifier, shorten=(initAddressee == None))
				else:
					cs = speak_callsign_commercial_flight(self.airline, self.identifier[len(self.airline):])
				msg = speech_str2tts(txt_message)
				if initAddressee == None:
					tts_struct = [msg, cs] if responding else [cs, msg]
				else: # explicitly addressing
					tts_struct = [initAddressee, cs, msg]
				signals.voiceMsg.emit(self, ', '.join(tts_struct)) # takes care of the RDF signal
			else: # Not synthesising voice, but should simulate a radio signal for RDF system
				env.rdf.receiveSignal(self.identifier, self.coords, timeOut=simulated_radio_signal_timeout)
	
	def ttsAppWanted(self, default=''):
		if self.wantsVisualApp():
			return 'visual'
		elif self.wantsILS():
			return '\\SPLIT_CHARS{ILS}'
		else: # this only happens sometimes in teacher mode
			return default
	
	def makeInitialContact(self, atc_tts_string):
		msg = 'Hello, '
		if self.statusType() == Status.READY:
			msg += 'short of runway \\RWY{%s}, ready for departure.' % self.params.status.arg
			
		elif self.statusType() == Status.LANDING:
			if self.wantsVisualApp():
				msg += 'on visual approach runway \\RWY{%s}' % self.params.status.arg
			else: # ILS
				msg += 'established \\SPLIT_CHARS{ILS} \\RWY{%s}' % self.params.status.arg
			
		elif self.statusType() == Status.TAXIING:
			if self.wantsToPark():
				msg += 'runway cleared, for parking at \\SPELL_ALPHANUMS{%s}' % self.goal
			else:
				if env.airport_data != None:
					pk = env.airport_data.ground_net.closestParkingPosition(self.params.position, maxdist=.1)
					if pk != None:
						msg += 'standing at \\SPELL_ALPHANUMS{%s}, ' % pk
				msg += 'ready to taxi'
		
		elif self.isInboundGoal():
			msg += '\\FL_ALT{%s}' % env.readStdAlt(self.params.altitude)
			msg += ', inbound for %s approach' % self.ttsAppWanted()
			instr = self.instrOfType(Instruction.EXPECT_RWY)
			if instr != None:
				msg += ' runway \\RWY{%s}' % instr.arg
			
		elif self.isOutboundGoal(): # Normally a departure received from TWR
			msg += 'passing \\FL_ALT{%s}' % env.readStdAlt(self.params.altitude)
			instr = self.instrOfType(Instruction.VECTOR_ALT)
			if instr != None:
				msg += ' for \\FL_ALT{%s}' % instr.arg
		
		else: # Transit for CTR
			msg += '\\FL_ALT{%s}' % env.readStdAlt(self.params.altitude)
		## Now SAY IT!
		self.say(msg, False, initAddressee=atc_tts_string)
	
	def readBack(self, instr_sequence):
		lst = []
		for instr in instr_sequence:
			if instr.type == Instruction.VECTOR_HDG:
				msg = 'Heading \\SPELL_ALPHANUMS{%s}' % instr.arg.read()
			elif instr.type == Instruction.VECTOR_ALT:
				msg = '\\FL_ALT{%s}' % instr.arg
			elif instr.type == Instruction.VECTOR_SPD:
				msg = '\\SPEED{%s}' % instr.arg
			elif instr.type == Instruction.VECTOR_DCT:
				msg = 'Direct \\NAVPOINT{%s}' % instr.arg.code
			elif instr.type == Instruction.CANCEL_VECTOR_SPD:
				msg = 'Speed my discretion'
			elif instr.type == Instruction.FOLLOW_ROUTE:
				msg = 'Copied route, now proceeding \\NAVPOINT{%s}' % instr.arg.currentWaypoint(self.params.position)
			elif instr.type == Instruction.HOLD:
				fix, turns = instr.arg
				msg = 'Hold at \\NAVPOINT{%s}, %s turns' % (fix.code, ('right' if turns else 'left'))
			elif instr.type == Instruction.SQUAWK:
				msg = '\\SPELL_ALPHANUMS{%04o}' % instr.arg
			elif instr.type == Instruction.CANCEL_APP:
				msg = 'Cancel approach'
			elif instr.type == Instruction.HAND_OVER:
				msg = 'With \\ATC{%s}, thank you, good bye.' % instr.arg[0]
			elif instr.type == Instruction.LINE_UP:
				msg = 'Line up and wait'
			elif instr.type == Instruction.INTERCEPT_NAV:
				msg = 'Intercept \\NAVPOINT{%s} \\SPELL_ALPHANUMS{%s}' % (instr.arg[0].code, instr.arg[1].read())
			elif instr.type == Instruction.INTERCEPT_LOC:
				msg = 'Intercept localiser \\RWY{%s}' % self.instrOfType(Instruction.EXPECT_RWY).arg
			elif instr.type == Instruction.EXPECT_RWY:
				if self.isGroundStatus():
					msg = 'Runway \\RWY{%s}, will report ready for departure' % instr.arg
				else:
					msg = 'Expecting \\RWY{%s} for %s approach' % (instr.arg, self.ttsAppWanted(default='the'))
			elif instr.type == Instruction.TAXI:
				if env.airport_data == None:
					msg = 'Unable to taxi'
				else:
					msg = env.airport_data.ground_net.taxiInstrStr(*instr.arg)
			elif instr.type == Instruction.HOLD_POSITION:
				msg = 'Hold position'
			elif instr.type == Instruction.CLEARED_APP:
				msg = 'Cleared %s \\RWY{%s}' % (self.ttsAppWanted(default='approach'), self.instrOfType(Instruction.EXPECT_RWY).arg)
			elif instr.type == Instruction.CLEARED_TKOF:
				msg = 'Cleared for take-off \\RWY{%s}' % self.params.status.arg
			elif instr.type == Instruction.CLEARED_TO_LAND:
				msg = 'Clear to land runway \\RWY{%s}' % self.instrOfType(Instruction.EXPECT_RWY).arg
			elif instr.type == Instruction.SAY_INTENTIONS:
				if self.wantsToPark():
					msg = 'Park at \\SPELL_ALPHANUMS{%s}' % self.goal
				elif self.isInboundGoal():
					msg = '%s approach' % self.ttsAppWanted()
					instr2 = self.instrOfType(Instruction.EXPECT_RWY)
					if instr2 != None:
						msg += ', expecting runway \\RWY{%s}' % instr2.arg
				elif self.isOutboundGoal():
					msg = 'Departing'
					if self.goal[0] != None:
						msg += ' via \\NAVPOINT{%s}' % self.goal[0].code
					if self.goal[1] != None:
						msg += ', cruise \\FL_ALT{%s}' % self.goal[1]
				elif isinstance(self.goal, Airfield): # Transiting with destination
					msg = 'En-route to \\SPELL_ALPHANUMS{%s}' % self.goal
				else:
					msg = 'No intentions'
			lst.append(msg)
		## Now SAY IT!
		self.say(', '.join(lst), True)
	
	
	## SNAPSHOTS
	
	def fromStatusSnapshot(snapshot): # STATIC constructor
		cs, t, params, goal, spawned, frozen, instr = snapshot
		acft = ControlledAircraft(cs, t, params.dup(), goal)
		acft.instructions = [i.dup() for i in instr]
		acft.spawned = spawned
		acft.frozen = frozen
		return acft
	
	def statusSnapshot(self):
		return self.identifier, self.aircraft_type, self.params.dup(), self.goal, \
				self.spawned, self.frozen, [i.dup() for i in self.instructions]
	
