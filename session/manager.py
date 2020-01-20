
import string, re
from random import random, randint, choice

from data.db import acft_cat, acft_registration_formats
from session.env import env


# ---------- Constants ----------

teacher_callsign = 'Teacher'
student_callsign = 'Student'

tail_number_letter_placeholder = '@'
tail_number_digit_placeholder = '%'
tail_number_alphanum_placeholder = '*'
rnd_callsign_max_attempts = 5
commercial_prob = {'heavy': 1, 'jets': .8, 'turboprops': .2, 'props': 0, 'helos': 0}

# -------------------------------

class SessionType:
	enum = DUMMY, SOLO, FLIGHTGEAR_MP, TEACHER, STUDENT = range(5)



class CallsignGenerationError(StopIteration):
	pass



class HandoverBlocked(Exception):
	def __init__(self, msg, silent=False):
		Exception.__init__(self, msg)
		self.silent = silent # e.g. explicitly cancelled by user

class CpdlcAuthorityTransferFailed(Exception):
	def __init__(self, acft_callsign, atc_callsign, msg):
		Exception.__init__(self, msg)
		self.acft_callsign = acft_callsign
		self.atc_callsign = atc_callsign



tail_number_letter_regexp = re.compile(re.escape(tail_number_letter_placeholder))
tail_number_digit_regexp = re.compile(re.escape(tail_number_digit_placeholder))
tail_number_alphanum_regexp = re.compile(re.escape(tail_number_alphanum_placeholder))


class SessionManager:
	'''
	Subclasses should redefine attributes:
		- session_type
		- has_online_FPLs (False by default)
	and the following silent methods:
		- start
		- stop
		- pauseSession
		- resumeSession
		- isRunning
		- myCallsign
		- getAircraft
		- postRadioChatMsg (raises ValueError if message should not appear as posted)
		- postAtcChatMsg (raises ValueError)
		- instructAircraftByCallsign
		- stripDroppedOnATC (raises HandoverBlocked is strip not sent)
		- sendCpdlcMsg # TODO? raise exception if no active connection for ACFT? (check all session types)
		- transferCpdlcAuthority (raises CpdlcAuthorityTransferFailed)
		- disconnectCpdlc
		- sendWhoHas
		- getWeather (weather for given argument station name)
		- pushFplOnline
		- changeFplStatus (never called if only None FPL statuses can exist in the session type)
	'''
	
	def __init__(self, gui):
		self.gui = gui
		self.session_type = SessionType.DUMMY
		self.has_online_FPLs = False

	def generateCallsign(self, acft_type, available_airlines):
		cs = None
		attempts = 0
		while cs == None or cs in env.ATCs.knownATCs() + [acft.identifier for acft in self.getAircraft()]:
			if attempts >= rnd_callsign_max_attempts:
				raise CallsignGenerationError('Max attempts reached in looking to randomise callsign.')
			attempts += 1
			airline = None
			if len(available_airlines) > 0:
				cat = acft_cat(acft_type)
				if cat != None and random() < commercial_prob.get(cat, 0):
					airline = choice(available_airlines)
			if airline == None:
				if len(acft_registration_formats) > 0:
					cs = choice(acft_registration_formats)
					cs = tail_number_letter_regexp.sub((lambda x: choice(string.ascii_uppercase)), cs)
					cs = tail_number_digit_regexp.sub((lambda x: choice(string.digits)), cs)
					cs = tail_number_alphanum_regexp.sub((lambda x: choice(string.ascii_uppercase + string.digits)), cs)
			else:
				cs = '%s%04d' % (airline, randint(1, 9999))
		return cs
	
	
	## Methods to override below ##
	
	def start(self):
		pass
	
	def stop(self):
		pass
	
	def pauseSession(self): # FIXME suspend WTC and CPDLC timeout timers when paused
		pass
	
	def resumeSession(self):
		pass
	
	def isRunning(self):
		return False
	
	def myCallsign(self):
		return 'Dummy'
	
	def getAircraft(self):
		return []
	
	def getWeather(self, station):
		return None
	
	def postRadioChatMsg(self, msg):
		pass
	
	def postAtcChatMsg(self, msg):
		pass
	
	def instructAircraftByCallsign(self, callsign, instr):
		pass
	
	def stripDroppedOnATC(self, strip, atc):
		return None
	
	def sendCpdlcMsg(self, callsign, msg):
		pass
	
	def transferCpdlcAuthority(self, acft_callsign, atc_callsign):
		pass
	
	def disconnectCpdlc(self, callsign):
		pass
	
	def sendWhoHas(self, callsign):
		pass
	
	def pushFplOnline(self, fpl):
		pass
	
	def changeFplStatus(self, fpl, new_status):
		pass

