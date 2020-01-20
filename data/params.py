
import re

from datetime import timedelta
from math import sqrt, cos, sin, atan2, radians, degrees

from session.config import settings
from data.util import some, rounded
from data.utc import duration_str


# ---------- Constants ----------

AMSL_reading_regexp = re.compile('(\\d+)( ?ft)?$', flags=re.IGNORECASE)
FL_reading_regexp = re.compile('FL ?(\\d+)$', flags=re.IGNORECASE)

min_significant_TTF_speed = 10 # kt

# -------------------------------




#--------------------------------------------#
#                                            #
#                 Headings                   #
#                                            #
#--------------------------------------------#


class Heading:
	# STATIC:
	declination = None
	
	def __init__(self, deg, true_hdg):
		'''
		deg is float angle in degrees with 0/360 North and counting clockwise
		true_hdg is a bool to choose between a true heading (True) or a magnetic heading (False)
		'''
		self.is_true = true_hdg
		self.deg_angle = deg % 360
	
	def __add__(self, a):
		return Heading(self.deg_angle + a, self.is_true)
	
	def trueAngle(self):
		return self.deg_angle if self.is_true else self.deg_angle + some(Heading.declination, 0)
	
	def magneticAngle(self):
		return self.deg_angle - some(Heading.declination, 0) if self.is_true else self.deg_angle
	
	def opposite(self):
		return Heading(self.deg_angle + 180, self.is_true)
		
	def read(self):
		'''
		as would be read by/to a pilot, returns a string
		'''
		return '%03d' % ((self.magneticAngle() - 1) % 360 + 1)
		
	def readTrue(self):
		return '%03d' % ((self.trueAngle() - 1) % 360 + 1)
	
	def diff(self, other, tolerance=0):
		diff = (self.trueAngle() - other.trueAngle() + 180) % 360 - 180
		if abs(diff) <= tolerance:
			return 0
		else:
			return diff
	
	def rounded(self, true_hdg, step=5):
		return Heading(rounded((self.trueAngle() if true_hdg else self.magneticAngle()), step), true_hdg)
	
	def approxCardinal(self, true):
		hdg = self.trueAngle() if true else self.magneticAngle()
		return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'S', 'NW'][int((hdg + 45 / 2) % 360 * 8 / 360)]






#---------------------------------------------#
#                                             #
#                 Altitudes                   #
#                                             #
#---------------------------------------------#


class StdPressureAlt:
	'''
	The class for pressure-altitudes, as are reported by a transponder
	'''
	
	#---
	# STATIC:
	def fromFL(fl):
		return StdPressureAlt(100 * fl)
	
	def fromAMSL(ftAMSL, qnh):
		'''
		Gives the XPDR/std pressure-alt of an altitude above sea level, measured in given MSL pressure conditions.
		'''
		return StdPressureAlt(ftAMSL + 28 * (1013.25 - qnh))
	
	def fromReading(reading, qnh):
		match = FL_reading_regexp.match(reading) # added '$' to end of regexp because fullmatches fail here (why?!)
		if match:
			return StdPressureAlt.fromFL(int(match.group(1)))
		match = AMSL_reading_regexp.match(reading)
		if match:
			return StdPressureAlt.fromAMSL(int(match.group(1)), qnh)
		raise ValueError('Bad reading: "%s"' % reading)
	
	def reformatReading(reading, unit=True):
		'''
		returns (bool reading OK, reformatted reading if possible)
		'''
		match = FL_reading_regexp.match(reading) # added '$' to end of regexp because fullmatches fail here (why?!)
		if match:
			return 'FL%03d' % int(match.group(1))
		match = AMSL_reading_regexp.match(reading)
		if match:
			return '%d%s' % (int(match.group(1)), (' ft' if unit else ''))
		raise ValueError(reading)
	#---
	
	def __init__(self, ft):
		self._ft = ft
	
	def __add__(self, diff):
		return StdPressureAlt(self.ft1013() + diff)
	
	def __sub__(self, d):
		return self + -d
	
	def ft1013(self):
		return self._ft
	
	def ftAMSL(self, qnh):
		return self._ft + 28 * (qnh - 1013.25)
	
	def FL(self):
		return int(self._ft / 100 + .5)

	def diff(self, other, tolerance=0):
		'''
		'other' must be a StdPressureAlt
		'''
		diff = self._ft - other._ft
		if abs(diff) <= tolerance:
			return 0
		else:
			return diff











#------------------------------------------#
#                                          #
#                 Speeds                   #
#                                          #
#------------------------------------------#

class Speed:
	'''
	A class for HORIZONTAL speeds, typically measured in knots
	'''
	def __init__(self, kt):
		self.kt = kt
		
	def __str__(self):
		return '%d kt' % rounded(self.kt)
	
	def __add__(self, d):
		return Speed(self.kt + d)
	
	def __sub__(self, d):
		return self + -d
	
	def __eq__(self, other):
		try: return self.kt == other.kt
		except AttributeError: return False
	
	def rounded(self, step=10):
		return Speed(rounded(self.kt, step))
	
	def diff(self, other, tolerance=0):
		diff = self.kt - other.kt
		if abs(diff) <= tolerance:
			return 0
		else:
			return diff
	
	def ias2tas(self, alt):
		return Speed(self.kt * (1 + 2e-5 * alt.ft1013())) # 2% TAS increase per thousand ft AMSL
	
	def tas2ias(self, alt):
		return Speed(self.kt / (1 + 2e-5 * alt.ft1013()))





def wind_effect(acft_hdg, acft_tas, wind_from_hdg, wind_speed):
	'''
	return (course, ground speed) pair from ACFT heading and TAS
	'''
	hdg = radians(acft_hdg.magneticAngle())
	tas = acft_tas.kt
	wd = radians(wind_from_hdg.magneticAngle())
	ws = wind_speed.kt
	ground_speed = sqrt(ws*ws + tas*tas - 2 * ws * tas * cos(hdg - wd))
	wca = atan2(ws * sin(hdg - wd), tas - ws * cos(hdg - wd))
	return Heading(degrees(hdg + wca), False), Speed(ground_speed)
	


def time_to_fly(dist, speed):
	if speed.kt < min_significant_TTF_speed:
		raise ValueError('Speed too low')
	return timedelta(hours = dist / speed.kt)



def distance_flown(time, speed):
	'''
	time is a timedelta object
	'''
	return time / timedelta(hours=1) * speed.kt



def TTF_str(dist, speed):
	return duration_str(time_to_fly(dist, speed))
