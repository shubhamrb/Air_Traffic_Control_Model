import re

from os import path

from data.ad import AirportData
from data.coords import EarthCoords
from data.params import Heading, Speed
from data.ad import DirRunway, Helipad
from data.nav import Navpoint, NavpointError, world_navpoint_db, world_routing_db
from data.db import acft_db, acft_registration_formats, phon_airlines, phon_navpoints
from data.elev import ElevationMap

from PyQt5.QtGui import QPixmap, QColor


# ---------- Constants ----------

aircraft_db_spec_file = 'resources/acft/acft-db'
aircraft_reg_spec_file = 'resources/acft/tail-numbers'
airlines_speech_file = 'resources/speech/airline-callsigns.phon'
airport_entry_exit_file = 'resources/nav/AD-entry-exit'
route_presets_file = 'resources/nav/route-presets'
background_images_dir = 'resources/bg-img'

elev_map_file_fmt = 'resources/elev/%s.elev'
navpoint_speech_file_fmt = 'resources/speech/navpoints/%s.phon'

pixmap_corner_sep = ':'
FG_ATC_model_token = ':ATC'
unavailable_acft_info_token = '-'

model_gnd_height_spec_token = ':height'
model_airline_livery_spec_token = ':airline'

# -------------------------------


def read_point_spec(specstr, db):
	mvlst = specstr.split('>')
	pbase = mvlst.pop(0)
	try:
		if ',' in pbase and '~' not in pbase:
			result = EarthCoords.fromString(pbase)
		else:
			result = navpointFromSpec(pbase, db).coordinates
	except NavpointError:
		raise ValueError('No navpoint for "%s" or navpoint not unique (consider using `~\' operator)' % pbase)
	else:
		while mvlst != []:
			mv = mvlst.pop(0).split(',')
			if len(mv) == 2:
				radial = Heading(float(mv[0]), True)
				distance = float(mv[1])
				result = result.moved(radial, distance)
			else:
				raise ValueError('Bad use of `>\' in point spec "%s"' % specstr)
		return result


navpoint_type_spec_regexp = re.compile(r"\((?P<type>.*)\)(?P<code>.*)")

def extractNavpointSpecType(specstr):
	'''
	Parse a navpoint with an optional type restriction of the form "(TYPE)CODE".
	Returns the navpoint code and a list of navpoint types to be used with "db.findX" methods.
	Raises a "ValueError" if TYPE is invalid.
	'''
	match = navpoint_type_spec_regexp.fullmatch(specstr)
	if match is None:
		return specstr, Navpoint.types
	else:
		return match.group('code'), [Navpoint.findType(match.group('type'))]


def navpointFromSpec(specstr, db):
	if '~' in specstr: # name closest to point spec
		name, near = specstr.split('~', maxsplit=1)
		name, nav_types = extractNavpointSpecType(name)
		return db.findClosest(read_point_spec(near, db), code=name, types=nav_types)
	else:
		name, nav_types = extractNavpointSpecType(specstr)
		return db.findUnique(name, types=nav_types)



##------------------------------------##
##                                    ##
##          BACKGROUND IMAGES         ##
##                                    ##
##------------------------------------##

def read_hand_drawing(file_name, db):
	try:
		with open(file_name, encoding='utf8') as f:
			draw_sections = []
			line = f.readline()
			while line != '':
				line = line.strip()
				if line != '':
					try:
						colour = QColor(line)
						if not colour.isValid():
							raise ValueError('Not a colour: ' + line)
						points = []
						tokens = f.readline().split(maxsplit=1)
						while len(tokens) != 0:
							text = tokens[1].strip() if len(tokens) == 2 else None
							points.append((read_point_spec(tokens[0], db), text))
							tokens = f.readline().split(maxsplit=1)
						if len(points) == 0:
							raise ValueError('No points in sequence')
					except (NavpointError, ValueError) as err: # error on line; 
						print('Drawing spec error in %s section %d: %s' % (file_name, len(draw_sections) + 1, err))
						while line != '': # skip until next empty line or EOF
							line = f.readline().strip()
					else:
						draw_sections.append((colour, points))
				line = f.readline()
		return draw_sections
	except FileNotFoundError:
		raise ValueError('Drawing file not found')


def read_bg_img(icao, db):
	try:
		with open(path.join(background_images_dir, '%s.lst' % icao), encoding='utf8') as f:
			radar_background_layers = []
			loose_strip_bay_backgrounds = []
			for line in f:
				tokens = line.strip().split(maxsplit=2)
				if len(tokens) == 3:
					try:
						image_file = path.join(background_images_dir, tokens[0])
						if tokens[1] == 'DRAW': # DRAWING SPEC, no corners given
							radar_background_layers.append((False, tokens[0], tokens[2], read_hand_drawing(image_file, db)))
						else:
							pixmap = QPixmap(image_file)
							if pixmap.isNull():
								raise ValueError('Not found or unrecognised format')
							if tokens[1] == 'LOOSE': # LOOSE STRIP BAY BACKGROUND
								new_tokens = tokens[2].split(maxsplit=1)
								if len(new_tokens) != 2:
									raise ValueError('Bad LOOSE spec (missing scale or title)')
								loose_strip_bay_backgrounds.append((tokens[0], pixmap, float(new_tokens[0]), new_tokens[1]))
							elif pixmap_corner_sep in tokens[1]: # PIXMAP, two corners given
								nw, se = tokens[1].split(pixmap_corner_sep, maxsplit=1)
								nw_coords = read_point_spec(nw, db)
								se_coords = read_point_spec(se, db)
								radar_background_layers.append((True, tokens[0], tokens[2], (pixmap, nw_coords, se_coords)))
							else:
								raise ValueError('Bad image spec (should be NW:SE or "DRAW")' + tokens[1])
					except ValueError as error:
						print('%s: %s' % (tokens[0], error))
				elif tokens != []:
					print('Bad syntax in background drawing spec line: ' + line)
		return radar_background_layers, loose_strip_bay_backgrounds
	except FileNotFoundError:
		print('No background image list found.')
		return [], []




##-----------------------------------##
##                                   ##
##       GROUND ELEVATION MAPS       ##
##                                   ##
##-----------------------------------##


def get_ground_elevation_map(location_code):
	try:
		with open(elev_map_file_fmt % location_code, encoding='utf8') as f:
			nw = se = None
			line = f.readline()
			while nw == None and line != '':
				tokens = line.split('#', maxsplit=1)[0].split()
				if tokens == []:
					line = f.readline()
				elif len(tokens) == 2:
					nw = EarthCoords.fromString(tokens[0])
					se = EarthCoords.fromString(tokens[1])
				else:
					raise ValueError('invalid header line')
			if nw == None:
				raise ValueError('missing header line')
			matrix = []
			xprec = None
			line = f.readline()
			while line.strip() != '':
				values = [float(token) for token in line.split('#', maxsplit=1)[0].split()]
				if xprec == None:
					xprec = len(values)
				elif len(values) != xprec:
					raise ValueError('expected %d values in row %d' % (xprec, len(matrix) + 1))
				matrix.append(values) # add row
				line = f.readline()
		# Finished reading file.
		result = ElevationMap(nw.toRadarCoords(), se.toRadarCoords(), len(matrix), xprec)
		for i, row in enumerate(matrix):
			for j, elev in enumerate(row):
				result.setElevation(i, j, elev)
		return result
	except ValueError as err:
		print('Error in elevation map: %s' % err)





##-----------------------------------------##
##                                         ##
##   AIRCRAFT DATA BASE + FGFS RENDERING   ##
##                                         ##
##-----------------------------------------##


def load_aircraft_db():
	'''
	loads the dict: ICAO desig -> (category, WTC, cruise speed)
	where category is either of those used in X-plane, e.g. for parking positions
	any of tuple elements can use the "unavailable_acft_info_token" to signify unknown info
	'''
	try:
		with open(aircraft_db_spec_file, encoding='utf8') as f:
			for line in f:
				tokens = line.split('#', maxsplit=1)[0].split()
				if len(tokens) == 4:
					desig, xplane_cat, wtc, cruise = tokens
					if xplane_cat == unavailable_acft_info_token:
						xplane_cat = None
					if wtc == unavailable_acft_info_token:
						wtc = None
					acft_db[desig] = xplane_cat, wtc, (Speed(float(cruise)) if cruise != unavailable_acft_info_token else None)
				elif tokens != []:
					print('Error on ACFT spec line: %s' % line.strip())
	except FileNotFoundError:
		print('Aircraft data base file not found: %s' % aircraft_db_spec_file)


def load_aircraft_registration_formats():
	try:
		with open(aircraft_reg_spec_file, encoding='utf8') as f:
			for line in f:
				tokens = line.split('#', maxsplit=1)[0].split()
				if len(tokens) == 1:
					acft_registration_formats.append(tokens[0])
				elif tokens != []:
					print('Error on ACFT tail number spec line: %s' % line.strip())
	except FileNotFoundError:
		print('Aircraft tail number spec file not found: %s' % aircraft_reg_spec_file)




def make_FGFS_model_recognisers(spec_file):
	res_acft = []
	res_atc = []
	try:
		with open(spec_file, encoding='utf8') as f:
			for line in f:
				tokens = line.split('#', maxsplit=1)[0].rsplit(maxsplit=1)
				if len(tokens) == 0: # empty line
					pass
				elif len(tokens) == 2: # new model recogniser
					try:
						regexp = re.compile(tokens[0], flags=re.IGNORECASE)
					except Exception as err: # CAUTION: greedy catch, but can only come from exceptions in re.compile
						print('Error in regexp for model %s: %s' % (model, err))
					else:
						if tokens[1] == FG_ATC_model_token:
							res_atc.append(regexp)
						else:
							res_acft.append((regexp, tokens[1]))
				else:
					print('Error on FGFS model recognising spec line: %s' % line.strip())
	except FileNotFoundError:
		print('FG model recognising spec file not found: %s' % spec_file)
	return res_acft, res_atc



def make_FGFS_model_chooser(spec_file):
	models = {}   # str -> str
	heights = {}  # str -> float
	liveries = {} # str -> (str -> str)
	last_dez = None
	try:
		with open(spec_file, encoding='utf8') as f:
			for line in f:
				tokens = line.split('#', maxsplit=1)[0].split()
				if len(tokens) == 0:
					continue
				if len(tokens) == 2 and tokens[0] == model_gnd_height_spec_token \
						and last_dez != None and last_dez not in heights:
					try:
						heights[last_dez] = float(tokens[1])
					except ValueError:
						print('Error on FGFS model height spec for %s: numerical expected; got "%s".' % (last_dez, tokens[1]))
				elif len(tokens) == 3 and tokens[0] == model_airline_livery_spec_token and last_dez != None:
					airline, livery = tokens[1:]
					if last_dez not in liveries: # first key for this ACFT type
						liveries[last_dez] = {}
					liveries[last_dez][airline] = livery
				elif len(tokens) == 2: # new model chooser
					dez, model = tokens
					models[dez] = model
					last_dez = dez
				else:
					print('Error on FGFS model choice line: %s' % line.strip())
					last_dez = None
	except FileNotFoundError:
		print('FG model chooser spec file not found: %s' % spec_file)
	return models, heights, liveries


##--------------------------------##
##                                ##
##          SPEECH STUFF          ##
##                                ##
##--------------------------------##

def load_speech_data_file(src_file, fill_dict, clearDict=True):
	try:
		with open(src_file, encoding='utf8') as f:
			if clearDict:
				fill_dict.clear()
			for line in f:
				cols = [column.strip() for column in line.split('#', maxsplit=1)[0].split('|')]
				if cols == ['']:
					pass
				elif len(cols) == 3 and all(col != '' for col in cols):
					code, callsign, phonemes = cols
					fill_dict[code] = callsign, phonemes
				else:
					print('ERROR in pronunciation spec line: %s' % line.strip())
	except FileNotFoundError:
		pass


def load_airlines_db():
	load_speech_data_file(airlines_speech_file, phon_airlines)

def load_local_navpoint_speech_data(location):
	load_speech_data_file(navpoint_speech_file_fmt % location, phon_navpoints)






##--------------------------------##
##                                ##
##           ROUTING DB           ##
##                                ##
##--------------------------------##


def import_entry_exit_data():
	try:
		with open(airport_entry_exit_file, encoding='utf8') as f:
			for line in f:
				tokens = line.split('#', maxsplit=1)[0].split()
				if len(tokens) == 0: # ignore empty lines
					continue
				elif len(tokens) >= 3: # AD "entry/exit" point_name
					try:
						ad = world_navpoint_db.findAirfield(tokens[0])
						p = world_navpoint_db.findClosest(ad.coordinates, code=tokens[2])
						if tokens[1] == 'entry':
							world_routing_db.addEntryPoint(ad, p, tokens[3:])
						elif tokens[1] == 'exit':
							world_routing_db.addExitPoint(ad, p, tokens[3:])
						else:
							print('Bad entry/exit line:', line)
					except NavpointError:
						print('Navpoint not found on entry/exit line:', line)
				else:
					print('Bad entry/exit line:', line)
	except FileNotFoundError:
		pass


def read_route_presets():
	result = {}
	try:
		with open(route_presets_file, encoding='utf8') as f:
			for line in f:
				spl = line.strip().split(maxsplit=2)
				if spl == [] or line.startswith('#'):
					pass # Ignore empty or comment lines
				elif len(spl) == 3:
					end_points = spl[0], spl[1]
					try:
						result[end_points].append(spl[2])
					except KeyError:
						result[end_points] = [spl[2]]
				else:
					print('Error on preset route line: %s' % line.strip())
	except FileNotFoundError:
		pass
	return result

