import re
from random import randint, choice

from PyQt5.QtCore import QThread

from data.db import phon_airlines, phon_navpoints, get_TTS_string

from session.config import settings
from session.env import env

try:
	import pyttsx3
	speech_synthesis_available = True
except ImportError:
	speech_synthesis_available = False


# ---------- Constants ----------

voice_rate_mean_value = 200 # words per minute
voice_rate_max_diff = 30 # words per minute

# Text-to-TTS backslashed command regexp groups: 1=command; 2=contents
TTS_cmd_regexp = re.compile('\\\\(\w+)\{([^}]*)\}')

# Alphanum word to spell regexp groups: none (take full match)
alphanum_word_regexp = re.compile('\\b[A-Z0-9]+\\b')

# -------------------------------



en_voices = [] # list of driver voice IDs (each of type bytes) capable of reading English


class PilotVoice:
	def __init__(self):
		'''
		raises IndexError if no voice ID available for English
		FUTURE: more voice features
		'''
		self.driver_id = choice(en_voices) # or IndexError if none in list
		self.rate = voice_rate_mean_value + randint(-voice_rate_max_diff, voice_rate_max_diff)



def new_voice():
	try:
		return PilotVoice()
	except IndexError:
		return None





class SpeechSynthesiser(QThread):
	def __init__(self, gui):
		'''
		raises ImportError if the driver is not installed
		'''
		QThread.__init__(self, gui)
		en_voices.clear()
		self.engine = pyttsx3.init(driverName=settings.TTS_driver)
		vdct = { v.id: set(lang.decode('utf8') for lang in v.languages) for v in self.engine.getProperty('voices') }
		en_voices.extend(vid for vid, langs in vdct.items() if any('en' in lang for lang in langs))
		self.engine.connect('finished-utterance', self.onFinishUtterance) # NOTE if needed: this returns a token enabling disconnect

	def startup(self):
		self.start()

	def shutdown(self):
		self.engine.endLoop()
		en_voices.clear()

	def run(self):
		self.engine.startLoop()

	def radioMsg(self, calling_acft, text):
		if not settings.session_start_sound_lock:
			self.engine.stop()
			QThread.msleep(100)
			self.engine.setProperty('voice', calling_acft.pilotVoice().driver_id)
			self.engine.setProperty('rate', calling_acft.pilotVoice().rate)
			env.rdf.receiveSignal(calling_acft.identifier, calling_acft.coords)
			self.engine.say(text, calling_acft.identifier) # callsign used as name for callback on end of utterance
		
	def onFinishUtterance(self, name, completed): # callback signature imposed by pyttsx3
		env.rdf.dieSignal(name) # name is the original caller, used as RDF signal key


# -------------------------------


def speech_str2txt(cmd_str):
	return TTS_cmd_regexp.sub((lambda match: match.group(2)), cmd_str)

def speech_str2tts(cmd_str):
	return TTS_cmd_regexp.sub((lambda match: tts_string(match.group(1), match.group(2))), cmd_str)


def tts_string(cmd, arg):
	if cmd == 'SPELL_ALPHANUMS':
		return alphanum_word_regexp.sub((lambda match: speak_alphanums(match.group(0))), arg)
	elif cmd == 'SPLIT_CHARS':
		return ' '.join(arg)
	elif cmd == 'RWY':
		if arg[-1] in 'LRC':
			return speak_alphanums(arg[:-1]) + ' ' + {'L': 'left', 'R': 'right', 'C': 'centre'}[arg[-1]]
		else:
			return speak_alphanums(arg)
	elif cmd == 'FL_ALT':
		digits = ''.join(d for d in arg if d.isdigit())
		if arg.startswith('FL'):
			return 'flight level ' + speak_alphanums(digits)
		else:
			alt = int(digits)
			h = (alt % 1000) // 100
			t = alt // 1000
			struct = [] if t == 0 else ['%s thousand' % t]
			if h != 0:
				struct.append('%s hundred' % h)
			return ' '.join(struct)
	elif cmd == 'SPEED':
		digits = ''.join(d for d in arg if d.isdigit())
		return speak_alphanums(digits) + ' knots'
	elif cmd == 'NAVPOINT':
		if arg in phon_navpoints:
			return get_TTS_string(phon_navpoints, arg)
		elif len(arg) < 5 and all(c.isupper() for c in arg):
			return speak_alphanums(arg)
		else:
			return arg
	elif cmd == 'ATC':
		return {
			'GND': 'ground',
			'TWR': 'tower',
			'DEP': 'departure',
			'APP': 'approach',
			'CTR': 'centre'
		}.get(arg, arg)
	else:
		print('Please report unsubstituted TTS cmd match: %s' % cmd)
		return arg






def speak_alphanums(s):
	return ' '.join(alphanum_tokens[tok] for tok in s)

def speak_callsign_tail_number(tail_number, shorten=False):
	str_split = tail_number.split('-')
	if shorten:
		tail = str_split[-1]
		if len(str_split) == 1:
			prefix = 'N' if tail.startswith('N') else ''
			tail = tail[len(prefix):]
		else:
			prefix = str_split[0]
		if len(tail) > 3: # shorten
			if tail[-2].isalpha() == tail[-1].isalpha():
				tail = tail[-2:]
			else:
				tail = tail[-3:]
		if len(prefix) >= 2 and len(tail) >= 3: # forget prefix
			prefix = ''
		return speak_alphanums(prefix + tail)
	else:
		return speak_alphanums(''.join(str_split))


def speak_callsign_commercial_flight(airline, flight_number):
	res = [get_TTS_string(phon_airlines, airline)]
	n = int(flight_number)
	n1 = n // 100
	n2 = n % 100
	if n1 != 0:
		res.extend(num_0_99(n1, fillTens=False))
	res.extend(num_0_99(n2, fillTens=True))
	return ' '.join(res)




## TOKENS

def num_0_99(n, spellDigits=False, fillTens=False):
	s = str(n)
	if spellDigits or n < 10:
		if fillTens and n < 10:
			s = '0' + s
		return [alphanum_tokens[c] for c in s]
	else: # group two digits
		return [s] # trust synthesiser
	

alphanum_tokens = {
	'A': 'alpha',
	'B': 'bravo',
	'C': 'charlie',
	'D': 'delta',
	'E': 'echo',
	'F': 'fox',
	'G': 'golf',
	'H': 'hotel',
	'I': 'india',
	'J': 'juliet',
	'K': 'kilo',
	'L': 'lima',
	'M': 'mike',
	'N': 'november',
	'O': 'oscar',
	'P': 'papa',
	'Q': 'quebec',
	'R': 'romeo',
	'S': 'sierra',
	'T': 'tango',
	'U': 'uniform',
	'V': 'victor',
	'W': 'whiskey',
	'X': 'x-ray',
	'Y': 'yankee',
	'Z': 'zulu',
	'0': 'zero',
	'1': 'one',
	'2': 'two',
	'3': 'three',
	'4': 'four',
	'5': 'five',
	'6': 'six',
	'7': 'seven',
	'8': 'eight',
	'9': 'niner'
}
