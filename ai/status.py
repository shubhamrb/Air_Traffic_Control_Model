
from data.params import StdPressureAlt

from session.config import settings
from session.env import env


# ---------- Constants ----------

default_XPDR_mode = 'C'

# -------------------------------

#
# Statuses and arg types
#
# On ground:
#  TAXIING
#  READY: str (RWY name)
#  LINED_UP: str (RWY name)
#  RWY_TKOF: str (RWY name)
#  RWY_LDG: str (RWY name), or None if skidded off RWY
# Off ground:
#  AIRBORNE
#  HLDG: Heading (outbound leg direction), timedelta (time left to fly outbound)
#  LANDING: str (RWY name)
#

class Status:
	enum = TAXIING, READY, LINED_UP, RWY_TKOF, AIRBORNE, HLDG, LANDING, RWY_LDG = range(8)
	
	def __init__(self, init_status, arg=None):
		'''
		Creates an airborne aircraft, unless RWY is given (starts ready for DEP)
		'''
		self.type = init_status
		self.arg = arg
	
	def __str__(self):
		arg_suffix = '' if self.arg == None else ':%s' % self.arg
		return 'S:%d%s' % (self.type, arg_suffix)
	
	def dup(self):
		return Status(self.type, arg=self.arg)
	



class SoloParams:
	
	def __init__(self, init_status, init_pos, init_alt, init_hdg, init_ias):
		self.status = init_status
		self.position = init_pos
		self.altitude = init_alt
		self.heading = init_hdg
		self.ias = init_ias
		self.XPDR_mode = default_XPDR_mode # possible values are: '0', 'A', 'C', 'S' ('S' may squat depending on ACFT setting)
		self.XPDR_code = settings.uncontrolled_VFR_XPDR_code
		self.XPDR_idents = False
		self.runway_reported_in_sight = False
		self.RWY_excursion_stage = 0  # 0 = not started; 1 = currently skidding; 2 = done skidding (crashed off RWY)
	
	def dup(self):
		params = SoloParams(self.status.dup(), self.position, self.altitude, self.heading, self.ias)
		params.XPDR_mode = self.XPDR_mode
		params.XPDR_code = self.XPDR_code
		params.XPDR_idents = self.XPDR_idents
		params.runway_reported_in_sight = self.runway_reported_in_sight
		params.RWY_excursion_stage = self.RWY_excursion_stage
		return params
	
	def geometricAltitude(self):
		return self.altitude.ftAMSL(env.QNH())

