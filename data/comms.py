
import re

from PyQt5.QtCore import pyqtSignal, QObject, QTimer

from data.util import some, noNone, pop_all, rounded
from data.coords import dist_str
from data.fpl import FPL
from data.utc import timestr, now
from data.weather import hPa2inHg
from data.strip import rack_detail, runway_box_detail, parsed_route_detail, \
		assigned_SQ_detail, assigned_altitude_detail, assigned_heading_detail, assigned_speed_detail

from session.env import env
from session.config import settings


# ---------- Constants ----------

text_alias_prefix = '$'
text_alias_failed_replacement_prefix = '!!'

# -------------------------------




# =============================================== #

#              TEXT CHAT AND ALIASES              #

# =============================================== #


class ChatMessage:
	def __init__(self, sender, text, recipient=None, private=False):
		self.sent_by = sender
		self.known_recipient = recipient
		self.text = text
		self.private = private
		if recipient == None and private:
			self.private = False
			print('WARNING: Cannot make message private without an identified recipient; made public.')
		self.msg_time_stamp = now()

	def txtOnly(self):
		return self.text

	def txtMsg(self):
		if self.known_recipient == None or self.known_recipient == '' or self.private:
			return self.text
		else:
			return '%s: %s' % (self.known_recipient, self.text)
	
	def isPrivate(self):
		return self.private

	def sender(self):
		return self.sent_by

	def recipient(self):
		return self.known_recipient
	
	def timeStamp(self):
		return self.msg_time_stamp
	
	def isFromMe(self):
		return self.sender() == settings.session_manager.myCallsign()
	
	def involves(self, name):
		return self.sender() == name or self.recipient() == name




##  ALIASES AND REPLACEMENTS  ##


text_alias_regexp = re.compile('%s(\w+)' % re.escape(text_alias_prefix))


def custom_alias_search(alias, text):
	try:
		lines = [line.strip() for line in text.split('\n')]
		return next(line.split('=', maxsplit=1)[1] for line in lines if line.startswith('%s=' % alias))
	except StopIteration:
		raise ValueError('Alias not found: %s%s' % (text_alias_prefix, alias))


def text_alias_replacement(text_alias, current_selection):
	alias = text_alias.lower()
	weather = env.primaryWeather()
	## Check for general alias
	if alias == 'ad':
		noNone(env.airport_data)
		return env.locationName()
	elif alias == 'atis':
		return noNone(settings.last_ATIS_recorded)
	elif alias == 'decl':
		return noNone(env.readDeclination())
	elif alias == 'elev':
		return '%d ft' % noNone(env.airport_data).field_elevation
	elif alias == 'frq':
		return str(noNone(settings.publicised_frequency))
	elif alias == 'icao':
		return settings.location_code
	elif alias == 'me':
		return settings.session_manager.myCallsign()
	elif alias == 'metar':
		return noNone(weather).METAR()
	elif alias == 'qfe':
		noNone(env.airport_data)
		return '%d' % env.QFE(noNone(env.QNH(noneSafe=False)))
	elif alias == 'qnh':
		return '%d' % noNone(env.QNH(noneSafe=False))
	elif alias == 'qnhg':
		return '%.2f' % (hPa2inHg * noNone(env.QNH(noneSafe=False)))
	elif alias == 'runways':
		noNone(env.airport_data)
		return env.readRunwaysInUse()
	elif alias == 'rwyarr':
		rwys = [rwy.name for rwy in noNone(env.airport_data).allRunways() if rwy.use_for_arrivals]
		if rwys == []:
			raise ValueError('No RWY marked for arrival')
		return ', '.join(rwys)
	elif alias == 'rwydep':
		rwys = [rwy.name for rwy in noNone(env.airport_data).allRunways() if rwy.use_for_departures]
		if rwys == []:
			raise ValueError('No RWY marked for departure')
		return ', '.join(rwys)
	elif alias == 'ta':
		return '%d ft' % env.transitionAltitude()
	elif alias == 'tl':
		noNone(env.QNH(noneSafe=False))
		return 'FL%03d' % env.transitionLevel()
	elif alias == 'utc':
		return timestr()
	elif alias == 'vis':
		return noNone(weather).readVisibility()
	elif alias == 'wind':
		return noNone(weather).readWind()
	else: # Check for selection-dependant alias
		strip = current_selection.strip
		acft = current_selection.acft
		if alias == 'cralt':
			return noNone(noNone(strip).lookup(FPL.CRUISE_ALT, fpl=True))
		elif alias == 'dest':
			return noNone(noNone(strip).lookup(FPL.ICAO_ARR, fpl=True))
		elif alias == 'dist':
			coords = noNone(acft).coords()
			return dist_str(noNone(env.airport_data).navpoint.coordinates.distanceTo(coords))
		elif alias == 'nseq':
			return str(env.strips.stripSequenceNumber(noNone(strip))) # rightly fails with ValueError if strip is loose
		elif alias == 'qdm':
			coords = noNone(acft).coords()
			return coords.headingTo(noNone(env.airport_data).navpoint.coordinates).read()
		elif alias == 'rack':
			return noNone(noNone(strip).lookup(rack_detail))
		elif alias == 'route':
			return noNone(noNone(strip).lookup(FPL.ROUTE, fpl=True))
		elif alias == 'rwy':
			box = noNone(noNone(strip).lookup(runway_box_detail))
			return env.airport_data.physicalRunwayNameFromUse(box) # code unreachable if env.airport_data == None
		elif alias == 'sq':
			sq = noNone(strip).lookup(assigned_SQ_detail)
			return '%04o' % noNone(sq)
		elif alias == 'valt':
			valt = noNone(strip).lookup(assigned_altitude_detail)
			return noNone(valt) # valt is a "reading"
		elif alias == 'vhdg':
			vhdg = noNone(strip).lookup(assigned_heading_detail)
			return noNone(vhdg).read()
		elif alias == 'vspd':
			vspd = noNone(strip).lookup(assigned_speed_detail)
			return str(noNone(vspd))
		elif alias == 'wpnext':
			coords = noNone(acft).coords()
			route = noNone(strip).lookup(parsed_route_detail)
			return str(noNone(route).currentWaypoint(coords))
		elif alias == 'wpsid':
			route = noNone(strip).lookup(parsed_route_detail)
			return noNone(noNone(route).SID())
		elif alias == 'wpstar':
			route = noNone(strip).lookup(parsed_route_detail)
			return noNone(noNone(route).STAR())
		else:
			## Check for custom alias, in order: general notes, location-specific notes, selected strip comments
			try:
				return custom_alias_search(alias, settings.general_notes)
			except ValueError:
				try:
					return custom_alias_search(alias, settings.local_notes)
				except ValueError:
					comments = noNone(noNone(strip).lookup(FPL.COMMENTS))
					return custom_alias_search(alias, comments)


def _match_repl_failsafe(alias_match, current_selection):
	try:
		return text_alias_replacement(alias_match.group(1), current_selection)
	except ValueError:
		return text_alias_failed_replacement_prefix + alias_match.group(1).upper()


def replace_text_aliases(text, current_selection, value_error_if_missing):
	if value_error_if_missing:
		repl = lambda match: text_alias_replacement(match.group(1), current_selection)
	else:
		repl = lambda match: _match_repl_failsafe(match, current_selection)
	return text_alias_regexp.sub(repl, text)









# =============================================== #

#          VOICE AND RADIO COMMUNICATIONS         #

# =============================================== #


class CommFrequency:
	spacing = .025 / 3 # 8.33 kHz
	
	def __init__(self, mhz):
		if isinstance(mhz, str):
			if '.' in mhz:
				dec_part = mhz.rsplit('.', maxsplit=1)[-1]
				if len(dec_part) == 2 and dec_part[-1] in '27': # ._2 and ._7 endings are shortened 25kHz-step freq's
					mhz += '5'
			self.mhz = rounded(float(mhz), CommFrequency.spacing)
			if abs(self.mhz) < 1e-6: # freq not even 1 Hz
				raise ValueError('invalid near-zero comm frequency')
		else:
			self.mhz = mhz
	
	def __str__(self):
		return '%0.3f' % self.mhz
	
	def MHz(self):
		return self.mhz
	
	def inTune(self, other):
		return abs(self.mhz - other.mhz) < CommFrequency.spacing / 2




class RadioDirectionFinder(QObject):
	signalChanged = pyqtSignal()
	
	def __init__(self, position_coords):
		QObject.__init__(self)
		self.coordinates = position_coords
		self.received_signals = [] # (key, get signal origin function) pairs
	
	def currentSignalRadial(self):
		try:
			return self.coordinates.headingTo(self.received_signals[0][1]())
		except IndexError:
			return None
	
	def receivingSignal(self, signal_key):
		return any(k == signal_key for k, f in self.received_signals)
	
	def receiveSignal(self, signal_key, fGetOrigin, timeOut=None):
		if settings.radio_direction_finding:
			self.received_signals.insert(0, (signal_key, fGetOrigin))
			if timeOut != None:
				QTimer.singleShot(1000 * timeOut.total_seconds(), lambda sig=signal_key: self.dieSignal(sig))
			self.signalChanged.emit()
	
	def dieSignal(self, signal_key):
		pop_all(self.received_signals, lambda sig: sig[0] == signal_key)
		self.signalChanged.emit()
	
	def clearAllSignals(self):
		self.received_signals.clear()
		self.signalChanged.emit()







# =============================================== #

#               DATA LINK MESSAGING               #

# =============================================== #


class CpdlcMessage:
	# STATIC
	types = REQUEST, INSTR, FREE_TEXT, ACK, REJECT = range(5)
	
	def type2str(msg_type):
		return {
				CpdlcMessage.REQUEST: 'REQUEST',
				CpdlcMessage.INSTR: 'INSTR',
				CpdlcMessage.FREE_TEXT: 'TEXT',
				CpdlcMessage.ACK: 'ACK',
				CpdlcMessage.REJECT: 'REJECT'
			}[msg_type]
	
	def fromText(from_me, text):
		sep = text.split(' ', maxsplit=1) # len(sep) is 1 or 2
		try:
			msg_type = next(t for t in CpdlcMessage.types if CpdlcMessage.type2str(t) == sep[0])
			return CpdlcMessage(from_me, msg_type, contents=(None if len(sep) == 1 else sep[1]))
		except StopIteration: # Fallback on free text if type is not recognised
			return CpdlcMessage(from_me, CpdlcMessage.FREE_TEXT, contents=text)
	
	# OBJECT METHODS
	def __init__(self, from_me, msg_type, contents=None):
		self.from_me = from_me  # True = sent by me to them; False otherwise
		self.msg_type = msg_type
		self.msg_contents = contents
		self.time_stamp = now()
	
	def isFromMe(self):
		return self.from_me
	
	def type(self):
		return self.msg_type
	
	def contents(self):
		return self.msg_contents
	
	def text(self):
		res = CpdlcMessage.type2str(self.msg_type)
		if self.msg_contents != None:
			res += ' ' + self.msg_contents
		return res
	
	def timeStamp(self):
		return self.time_stamp
