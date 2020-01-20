
from data.params import Speed


# ---------- Constants ----------

take_off_speed_factor = 1.3 # mult. stall speed
touch_down_speed_factor = 1.1 # mult. stall speed

max_overspeed_prop = 10 # speed over cruising speed
max_overspeed_jet = 25 # speed over cruising speed

stall_speed_factors = {'heavy': .25, 'jets': .22, 'turboprops': .37, 'props': .52} # helos dealt with separately (no low-speed stall)

# -------------------------------


acft_db = {} # ICAO -> X-plane cat, WTC, cruise speed
acft_registration_formats = []


##  PRONUNCIATION DICTIONARIES: code -> (TTS str, SR phoneme list)  ##

phon_airlines = {}
phon_navpoints = {}


def get_TTS_string(dct, key):
	return dct[key][0]

def get_phonemes(dct, key):
	return dct[key][1]





def known_aircraft_types():
	return set(acft_db.keys())

def known_airline_codes():
	return list(phon_airlines)




def _get_info(t, i):
	try:
		return acft_db[t][i]
	except KeyError:
		return None

def acft_cat(t):
	return _get_info(t, 0)

def wake_turb_cat(t):
	return _get_info(t, 1)

def cruise_speed(t):
	return _get_info(t, 2)

def stall_speed(t):
	cat = acft_cat(t)
	if cat == 'helos':
		return None
	else:
		fact = stall_speed_factors.get(cat, None)
		crspd = cruise_speed(t)
		return Speed(fact * crspd.kt) if fact != None and crspd != None else None

def maximum_speed(t):
	crspd = cruise_speed(t)
	over = max_overspeed_jet if acft_cat(t) in ['heavy', 'jets'] else max_overspeed_prop
	return crspd + over if crspd != None else None

def take_off_speed(t):
	stall = stall_speed(t)
	return Speed(take_off_speed_factor * stall.kt) if stall != None else None

def touch_down_speed(t):
	stall = stall_speed(t)
	return Speed(touch_down_speed_factor * stall.kt) if stall != None else None
