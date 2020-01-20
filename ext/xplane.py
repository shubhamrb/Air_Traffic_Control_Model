
import re
from math import tan, radians

from session.config import version_string
from data.ad import AirportData, GroundNetwork
from data.coords import EarthCoords
from data.params import Heading
from data.comms import CommFrequency
from data.nav import Navpoint, Airfield, VOR, NDB, Fix, Rnav, NavpointError, world_navpoint_db, world_routing_db
from data.ad import DirRunway, Helipad

from PyQt5.QtGui import QPainterPath


# ---------- Constants ----------

custom_airport_file_fmt = 'resources/apt/%s.dat'
custom_ad_pos_file = 'resources/nav/custom_ad'
custom_navaid_file = 'resources/nav/custom_navaid'
custom_navfix_file = 'resources/nav/custom_fix'
custom_airway_file = 'resources/nav/custom_awy'

fallback_world_apt_dat_file = 'resources/x-plane/apt.dat'
fallback_navaid_file = 'resources/x-plane/earth_nav.dat'
fallback_navfix_file = 'resources/x-plane/earth_fix.dat'
fallback_airway_file = 'resources/x-plane/earth_awy.dat'

extracted_ad_pos_file = 'resources/apt.extract/AD-positions-names.extract'
extracted_airport_file_fmt = 'resources/apt.extract/%s.extract'
extracted_airport_file_line2 = 'Extracted by ATC-pie version %s from the full world "apt.dat" file' % version_string

awy_wp_max_dist = 15 # maximum distance at which to accept a waypoint name, in NM from its specified position

# -------------------------------


surface_types = {
	1: 'Asphalt',
	2: 'Concrete',
	3: 'Turf/grass',
	4: 'Dirt',
	5: 'Gravel',
	12: 'Dry lake bed',
	13: 'Water',
	14: 'Snow/ice',
	15: 'Transparent'
}


# ============================================== #

#            X-PLANE HELPER FUNCTIONS            #

# ============================================== #


def line_code(line):
	try:
		return int(line.split(maxsplit=1)[0])
	except (IndexError, ValueError):
		return None


def is_paved_surface(surface_code):
	return surface_code == 1 or surface_code == 2

def is_xplane_airport_header(line, icao=None):
	return line_code(line) in [1, 16, 17] and (icao == None or line.split(maxsplit=5)[4] == icao)

def is_xplane_node_line(line):
	return line_code(line) in range(111, 117)







def extend_path(path, end_point, prev_bezier, this_bezier):
	if this_bezier == None:
		if prev_bezier == None: # straight line
			path.lineTo(end_point)
		else:                   # bezier curve from last ctrl point
			path.quadTo(prev_bezier, end_point)
	else:
		mirror_ctrl = 2 * end_point - this_bezier
		if prev_bezier == None: # bezier curve to point with ctrl point
			path.quadTo(mirror_ctrl, end_point)
		else:                   # cubic bezier curve using ctrl points on either side
			path.cubicTo(prev_bezier, mirror_ctrl, end_point)
	



def parse_xplane_node_line(line):
	'''
	returns a 5-value tuple:
	- node position
	- bezier ctrl point if not None
	- int paint type if not None
	- int light type if not None
	- bool if ending node (True if closes path), or None if path goes on
	'''
	if not is_xplane_node_line(line):
		raise ValueError('Not a node line: %s' % line)
	tokens = line.split()
	row_code = tokens[0]
	node_coords = EarthCoords(float(tokens[1]), float(tokens[2])).toQPointF()
	bezier_ctrl = EarthCoords(float(tokens[3]), float(tokens[4])).toQPointF() if row_code in ['112', '114', '116'] else None
	ending_spec = None if row_code in ['111', '112'] else row_code in ['113', '114']
	paint_lights = [int(tk) for tk in tokens[3 if bezier_ctrl == None else 5:]]
	paint_type = next((t for t in paint_lights if t < 100), None)
	light_type = next((t for t in paint_lights if t >= 100), None)
	return node_coords, bezier_ctrl, paint_type, light_type, ending_spec
	


def read_xplane_node_sequence(f, first_line=None):
	'''
	Returns a tuple of:
	 - QPainterPath containing node sequence
	 - paint_sequence (length is same as path if closed; one item shorter otherwise)
	 - bool path is closed
	 - int number of lines read
	'''
	path = QPainterPath()
	lines_read = 0
	line = first_line
	if line == None:
		line = f.readline()
		lines_read += 1
	node, bez, paint, light, end_mode = parse_xplane_node_line(line.strip())
	assert end_mode == None, 'First node of path shold not be an ending node'
	first_node = node
	first_bezier = bez
	paint_sequence = [paint]
	path.moveTo(node)
	prev_bezier = bez
	while line != '':
		node, bez, paint, light, end_mode = parse_xplane_node_line(line.strip())
		extend_path(path, node, prev_bezier, bez)
		prev_bezier = bez
		if end_mode == None: # not yet reached end or loop
			paint_sequence.append(paint)
			line = f.readline()
			lines_read += 1
		else: # end of path reached
			if end_mode: # close loop (back to first point)
				extend_path(path, first_node, bez, first_bezier)
				paint_sequence.append(paint)
			return path, paint_sequence, end_mode, lines_read
	else:
		print('End of file: missing ending node')







# =============================================== #

#     OPENING & EXTRACTING NAV/AD DATA FILES      #

# =============================================== #


def open_airport_file(ad_code):
	try:
		return open(custom_airport_file_fmt % ad_code, encoding='utf8')
	except FileNotFoundError: # No custom airport file found; fall back on packaged X-plane data.
		extracted_airport_file_name = extracted_airport_file_fmt % ad_code
		try:
			return open(extracted_airport_file_name, encoding='utf8')
		except FileNotFoundError: # Airport never extracted yet; build simple file first.
			with open(fallback_world_apt_dat_file, encoding='iso-8859-15') as f: # WARNING: X-plane data encoded in ISO-8859-15
				line = line1 = f.readline()
				while line != '' and not is_xplane_airport_header(line, icao=ad_code):
					line = f.readline()
				if line != '': # not EOF
					with open(extracted_airport_file_name, 'w', encoding='utf8') as out:
						out.write(line1)
						out.write(extracted_airport_file_line2 + '\n\n')
						out.write(line)
						line = f.readline()
						while line != '' and not is_xplane_airport_header(line):
							out.write(line)
							line = f.readline()
			# Now file should exist
			return open(extracted_airport_file_name, encoding='utf8')



def open_ad_positions_file():
	try:
		return open(custom_ad_pos_file, encoding='utf8')
	except FileNotFoundError: # No custom airfield position file found; fall back on extracted X-plane inventory.
		try:
			return open(extracted_ad_pos_file, encoding='utf8')
		except FileNotFoundError: # Airport positions not extracted yet; build file from packaged X-plane world file.
			with open(fallback_world_apt_dat_file, encoding='iso-8859-15') as f: # WARNING: X-plane data encoded in ISO-8859-15
				with open(extracted_ad_pos_file, 'w', encoding='utf8') as exf:
					line = f.readline()
					ad_count = 0
					while line != '': # not EOF
						if is_xplane_airport_header(line):
							row_code, ignore1, ignore2, ignore3, icao_code, long_name = line.split(maxsplit=5)
							if icao_code.isalpha(): # Ignoring airports with numbers in them---to many of them, hardly ever useful
								# we are inside the airport section looking for its coordinates
								coords = None
								line = f.readline()
								while line != '' and not is_xplane_airport_header(line):
									if line_code(line) == 14: # X-plane viewpoint, unconditionally used as coords
										row_code, lat, lon, ignore_rest_of_line = line.split(maxsplit=3)
										coords = EarthCoords(float(lat), float(lon))
									elif coords == None and line_code(line) == 100: # falls back near a RWY end if no viewpoint for AD
										tokens = line.split()
										coords = EarthCoords(float(tokens[9]), float(tokens[10])).moved(Heading(360, True), .15)
									line = f.readline()
								if coords != None: # Airfields with unknown world coordinates are ignored
									exf.write('%s %s %s\n' % (icao_code, coords.toString(), long_name.strip()))
									ad_count += 1
							else:
								line = f.readline()
						else:
							line = f.readline()
					# Terminate with the footer to mark a finished process
					exf.write('%d\n' % ad_count)
			# Now file should exist
			return open(extracted_ad_pos_file, encoding='utf8')


def open_data_file_fallback(custom_file, fallback_file):
	try:
		return open(custom_file, encoding='utf8')
	except FileNotFoundError:
		return open(fallback_file, encoding='iso-8859-15') # WARNING: X-plane data encoded in ISO-8859-15







# =========================================== #

#          NAVIGATION & ROUTING DATA          #

# =========================================== #

def import_airfield_data():
	footer_line_count = None
	ad_added = 0
	with open_ad_positions_file() as f:
		for line in f:
			if line.startswith('#'):
				continue
			split = line.split(maxsplit=2)
			if len(split) == 3:
				icao_code, lat_lon, name = split
				coords = EarthCoords.fromString(lat_lon)
				world_navpoint_db.add(Airfield(icao_code, coords, name.strip()))
				ad_added += 1
			elif len(split) == 0:
				continue
			elif len(split) == 1 and footer_line_count == None:
				footer_line_count = int(split[0])
			else:
				raise ValueError('Bad or illegal spec line in AD positions file: %s' % line.strip())
	if footer_line_count == None or footer_line_count != ad_added:
		print('ERROR: inconsistencies detected in the AD positions file.')
		print('This is usually caused by an interrupted extraction process. ' \
			'Running the "cleanUp.sh" script should solve the problem in this case.')
		raise ValueError('AD data corrupt')


def import_navaid_data():
	with open_data_file_fallback(custom_navaid_file, fallback_navaid_file) as f:
		dmelst = [] # list of DMEs to try to couple with NDBs/VOR(TAC)s
		for line in f:
			if line_code(line) in [2, 3]: # NDB or VOR
				row_code, lat, lon, ignore1, frq, ignore2, ignore3, short_name, xplane_name = line.split(maxsplit=8)
				long_name = xplane_name.strip()
				coords = EarthCoords(float(lat), float(lon))
				if row_code == '2': # NDB
					world_navpoint_db.add(NDB(short_name, coords, frq, long_name))
				else: # VOR/VORTAC
					is_vortac = 'VORTAC' in long_name
					world_navpoint_db.add(VOR(short_name, coords, '%s.%s' % (frq[:3], frq[3:]), long_name, tacan=is_vortac))
			elif line_code(line) in [12, 13]: # DME: 12 = coupled with VOR/VORTAC; 13 = standalone or coupled with NDB
				row_code, lat, lon, ignore1, ignore2, ignore3, ignore4, short_name, xplane_name = line.split(maxsplit=8)
				coords = EarthCoords(float(lat), float(lon))
				t = Navpoint.VOR if row_code == '12' else Navpoint.NDB
				dmelst.append((short_name, coords, t))
		for name, pos, t in dmelst:
			try:
				p = world_navpoint_db.findClosest(pos, code=name, types=[t])
				p.dme = True
			except NavpointError:
				#debug('Not coupling DME for:', name, t)
				pass


# navfix_data_file example line:
# 49.137500  004.049167 DIKOL
#   lat        lon      name
navfix_line_regexp = re.compile('([0-9.-]+) +([0-9.-]+) +([A-Za-z0-9]+)')

def import_navfix_data():
	with open_data_file_fallback(custom_navfix_file, fallback_navfix_file) as f:
		for line in f:
			match = navfix_line_regexp.search(line)
			if match: # Fix spec line
				lat = float(match.group(1))
				lon = float(match.group(2))
				name = match.group(3)
				coordinates = EarthCoords(lat, lon)
				if name.isalpha() and len(name) == 5:
					world_navpoint_db.add(Fix(name, coordinates))
				else:
					world_navpoint_db.add(Rnav(name, coordinates))



# airway_data_file example line:
# DIKEN  65.053333  076.696667 INROS  65.403333  073.503333  1   282   397   G719
#  p1      lat1        lon1     p2      lat2       lon2   hi/lo FLmin FLmax AWY_name

def import_airway_data():
	with open_data_file_fallback(custom_airway_file, fallback_airway_file) as f:
		for line in f:
			tokens = line.split()
			if len(tokens) == 10:
				p1, lat1, lon1, p2, lat2, lon2, hi_lo, fl_lo, fl_hi, awy_name = tokens
				try:
					navpoint1 = world_navpoint_db.findClosest(EarthCoords(float(lat1), float(lon1)), code=p1, maxDist=awy_wp_max_dist)
					navpoint2 = world_navpoint_db.findClosest(EarthCoords(float(lat2), float(lon2)), code=p2, maxDist=awy_wp_max_dist)
					world_routing_db.addAwy(navpoint1, navpoint2, awy_name, fl_lo, fl_hi)
					world_routing_db.addAwy(navpoint2, navpoint1, awy_name, fl_lo, fl_hi) # FUTURE better data with unidirectional AWYs
				except NavpointError:
					#DEBUGprint('Ignoring AWY %s' % awy_name)
					pass




# =============================================== #

#                  AIRPORT DATA                   #

# =============================================== #


def get_airport_data(icao):
	result = AirportData()
	result.navpoint = world_navpoint_db.findAirfield(icao)
	
	# START WITH SIMPLE ONE-LINERS
	with open_airport_file(icao) as f:
		for line in f:
			row_type = line_code(line)
			
			if is_xplane_airport_header(line): # HEADER LINE; get elevation
				tokens = line.split(maxsplit=2)
				result.field_elevation = float(tokens[1])
				
			elif row_type == 100: # RUNWAY
				tokens = line.split()
				width = float(tokens[1])
				surface = int(tokens[2])
				name, lat, lon, disp_thr = tokens[8:12]
				rwy1 = DirRunway(name, EarthCoords(float(lat), float(lon)), float(disp_thr))
				name, lat, lon, disp_thr = tokens[17:21]
				rwy2 = DirRunway(name, EarthCoords(float(lat), float(lon)), float(disp_thr))
				result.addPhysicalRunway(width, surface, rwy1, rwy2)
				
			elif row_type == 102: # HELIPAD
				tokens = line.split()
				row_code, name, lat, lon, ori, l, w, surface = tokens[:8]
				centre = EarthCoords(float(lat), float(lon))
				result.helipads.append(Helipad(name, centre, int(surface), float(l), float(w), Heading(float(ori), True)))
				
			elif row_type == 14: # VIEWPOINT (NOTE: ATC-pie allows for more than one, though X-plane specifies one or zero)
				row_code, lat, lon, height, ignore, name = line.split(maxsplit=5)
				result.viewpoints.append((EarthCoords(float(lat), float(lon)), float(height), name.strip()))
				
			elif row_type == 19: # WINDSOCK
				row_code, lat, lon, ignore_rest_of_line = line.split(maxsplit=3)
				result.windsocks.append(EarthCoords(float(lat), float(lon)))
				
			elif row_type == 1302: # METADATA RECORD
				tokens = line.split()
				if len(tokens) == 3 and tokens[1] == 'transition_alt':
					result.transition_altitude = int(tokens[2])
	
	# NOW COMPLEX MULTI-LINE READS
	result.ground_net = get_ground_network(icao)
	
	return result


# X-PLANE runway line example:
# 100 29.87 1 1 0.00 0 2 1 07L 48.75115000 002.09846100 0.00 178.61 2 0 0 1 25R 48.75439400 002.11289900 0.00 0.00 2 1 0 0
#
# In order:
# 0: "100" for land RWY
# 1: width-metres
# 2: surface type
# 3-7: (ignore)
# 8-16 (RWY 1): name lat-end lon-end disp-thr-metres (ignore) (ignore) (ignore) (ignore) (ignore)
# 17-25 (RWY 2): (idem 8-16)


# X-PLANE helipad line example:
# 102 H1 47.53918248 -122.30722302 2.00 10.06 10.06 1 0 0 0.25 0
#
# In order:
# 0: "102" for helipad
# 1: name/designator
# 2-3: lat-lon of centre
# 4: true heading orientation
# 5-6: length-width (metres)
# 7: surface type
# 8-11: (ignore)


# X-PLANE viewpoint line example:
# 14   37.61714303 -122.38327660  200 0 Tower Viewpoint
#
# In order:
# 0: "14" for viewpoint
# 1-2: lat-lon coordinates
# 3: viewpoint height in ft
# 4: (ignored)
# 5: name


# X-PLANE windsock line example:
# 19  48.71901305  002.37906976 1 New Windsock 02
#
# In order:
# 0: "19" for windsock
# 1-2: lat-lon coordinates
# 3: has lighting
# 4: name






# X-PLANE frequency line example:
# 50 11885 ATIS
#
# In order:
# 0: freq type: 50=recorded (e.g. ATIS), 51=unicom, 52=DEL, 53=GND, 54=TWR, 55=APP, 56=DEP
# 1: integer frequency in 100*Hz
# 2: description

def get_frequencies(icao):
	with open_airport_file(icao) as f:
		result = []
		for line in f:
			tokens = line.split(maxsplit=2)
			if tokens != []:
				try:
					comm_freq = CommFrequency('%s.%s' % (tokens[1][:3], tokens[1][3:])) # using a str so that it is correctly converted to an 8.33kHz-spaced freq
					freq_type = { '50':'recorded', '51':'A/A', '52':'DEL', '53':'GND', '54':'TWR', '55':'APP', '56':'DEP' }[tokens[0]]
					result.append((comm_freq, tokens[2].strip(), freq_type))
				except (ValueError, KeyError, IndexError):
					pass
	return sorted(result, key=(lambda frqdata: str(frqdata[0])))




def get_airport_boundary(ICAO):
	with open_airport_file(ICAO) as f:
		result = []
		line = f.readline()
		line_number = 1
		while line != '' and not line_code(line) == 130: # Airport boundary section
			line = f.readline()
			line_number += 1
		if line != '':
			path, _, closed, lines_read = read_xplane_node_sequence(f)
			line_number += lines_read
			if not closed:
				print('Line %d: Boundary should end with a closing node' % line_number)
			return path


def get_taxiways(ICAO):
	'''
	returns a list of (descr str, surface int code, QPainterPath) tuples
	Each tuple defines a taxiway, to be drawn with the QPainterPath.
	'''
	with open_airport_file(ICAO) as f:
		result = []
		line = f.readline()
		line_number = 1
		while line != '': # not EOF
			if line_code(line) == 110: # TWY section
				header_tokens = line.strip().split(maxsplit=4)
				#Replaced because of dodgy data found at VHXX: row_code, surface, ignore1, ignore2, descr = header_tokens
				surface = int(header_tokens[1])
				descr = header_tokens[4] if len(header_tokens) == 5 else ''
				#print('Reading TWY section: %s' % descr)
				twy_path, _, closed, lines_read = read_xplane_node_sequence(f)
				line_number += lines_read
				if not closed:
					print('Line %d: X-plane taxiway should end with a closing node' % line_number)
				# Read holes on this TWY:
				line = f.readline()
				line_number += 1
				while is_xplane_node_line(line):
					hole_path, _, closed, lines_read = read_xplane_node_sequence(f, first_line=line)
					line_number += lines_read
					if not closed:
						print('Line %d: TWY hole should end with a closing node' % line_number)
					twy_path.addPath(hole_path)
					line = f.readline() # for new loop (more holes)
					line_number += 1
				result.append((descr, surface, twy_path))
			else:
				line = f.readline() # for new loop (more TWYs)
				line_number += 1
	return result
	



def get_airport_linear_objects(icao):
	with open_airport_file(icao) as f:
		holding_lines = []
		twy_centre_lines = []
		line = f.readline()
		line_number = 1
		while line != '': # not EOF
			if line_code(line) == 120: # Linear feature; header can contain a name (ignored here)
				path, paint_sequence, closed, lines_read = read_xplane_node_sequence(f)
				line_number += lines_read
				if any(t in [4, 5, 6, 54, 55, 56] for t in paint_sequence): # holding line
					holding_lines.append(path)
				elif any(t in [1, 7, 51, 57] for t in paint_sequence): # TWY centre line
					twy_centre_lines.append(path)
				#elif any(t in [2, 8, 9, 52, 58, 59] for t in paint_sequence): # other non TWY edge lines
				#	print(paint_sequence)
				#	.append(path)
			line = f.readline() # for more linear objects
			line_number += 1
	return holding_lines, twy_centre_lines



# Example of TAXIWAY NODE spec line
#   1201 47.53752190 -122.30826710 both 5416 A_start
# Columns:
#   1-2: lat-lon
#   4: ID

# Example of TAXIWAY EDGE spec line
#   1202 5416 5417 twoway taxiway A
# Columns:
#   1-2: vertices
#   4: "taxiway" or "runway" if on runway
#   5: TWY name

# Example of PARKING POSITION spec line
#   1300 47.43931757 -122.29806851 88.78 gate jets|turboprops A2
# Columns:
#   1-2: lat-lon
#   3: true heading when ACFT is parked
#   4: "gate", "hangar", "misc" or "tie-down" ("misc" not considered as parking)
#   5: pipe-deparated list heavy|jets|turboprops|props|helos or "all"
#   6: unique name of position


def get_ground_network(icao):
	with open_airport_file(icao) as f:
		ground_net = GroundNetwork()
		source_edges = [] # GroundNetwork pretty labelling breaks if we add duplicate edges
		line = f.readline()
		line_number = 1
		while line != '': # not EOF
			if line_code(line) == 1201: # TWY node
				tokens = line.strip().split(maxsplit=5)
				lat, lon, ignore, nid = tokens[1:5]
				ground_net.addNode(nid, EarthCoords(float(lat), float(lon)))
			elif line_code(line) == 1202: # TWY edge
				tokens = line.strip().split(maxsplit=5)
				v1, v2 = tokens[1:3]
				twy_name = rwy_spec = None
				if len(tokens) == 6:
					if tokens[4] == 'runway':
						rwy_spec = tokens[5].rstrip()
					elif tokens[4].startswith('taxiway'): # can be suffixed with "_X" to specify wing span
						twy_name = tokens[5].rstrip()
				if {v1, v2} in source_edges:
					print('WARNING: Ignoring duplicate ground route edge (%s, %s) in airport data file.' % (v1, v2))
				else:
					source_edges.append({v1, v2})
					try:
						ground_net.addEdge(v1, v2, rwy_spec, twy_name)
					except KeyError:
						print('Line %d: Invalid node for taxiway edge spec' % line_number)
			elif line_code(line) == 1300: # parking_position
				tokens = line.strip().split(maxsplit=6)
				if len(tokens) == 7:
					lat, lon, hdg, typ, who, pkid = tokens[1:7]
					if typ in ['gate', 'hangar', 'tie-down']:
						pos = EarthCoords(float(lat), float(lon))
						cats = [] if who == 'all' else who.split('|')
						ground_net.addParkingPosition(pkid, pos, Heading(float(hdg), True), typ, cats)
				else:
					print('Line %d: Invalid parking position spec' % line_number)
			line = f.readline() # for new loop (more TWYs)
			line_number += 1
		return ground_net




def import_ILS_capabilities(airport_data):
	with open_data_file_fallback(custom_navaid_file, fallback_navaid_file) as f:
		for line in f:
			# all lines with ILS codes [4..9] have similar structure:
			tokens = line.split(maxsplit=10)
			if not (len(tokens) == 11 and tokens[0] in '456789'):
				continue
			row_code, lat, lon, elev, frq, rng, qdm, ignore, ad, rwy, last_to_strip = tokens
			if ad == airport_data.navpoint.code:
				try:
					drwy = airport_data.runway(rwy)
					coords = EarthCoords(float(lat), float(lon))
				except KeyError: # unknown RWY
					print('Unknown RWY %s or bad LOC spec' % rwy)
				else: # we are interested in the line spec
					if row_code in ['4', '5']: # LOC
						drwy.ILS_cat = last_to_strip.strip()
						drwy.LOC_freq = '%s.%s' % (frq[:3], frq[3:])
						drwy.LOC_bearing = Heading(float(qdm), True)
						drwy.LOC_range = drwy.threshold(dthr=True).distanceTo(coords.moved(drwy.LOC_bearing.opposite(), float(rng)))
					elif row_code == '6': # GS (angle prefixes the bearing)
						try:
							iqdm = qdm.index('.') - 3
						except ValueError:
							iqdm = len(qdm) - 3
						fpa_degrees = int(qdm[:iqdm]) / 100
						drwy.param_FPA = 100 * tan(radians(fpa_degrees))
						drwy.GS_range = drwy.threshold(dthr=True).distanceTo(coords.moved(Heading(float(qdm[iqdm:]), True).opposite(), float(rng)))
					elif row_code == '7': # OM
						drwy.OM_pos = coords
					elif row_code == '8': # MM
						drwy.MM_pos = coords
					elif row_code == '9': # IM
						drwy.IM_pos = coords




