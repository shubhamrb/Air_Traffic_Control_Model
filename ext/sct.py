
import re
from random import randint

from session.config import settings
from session.env import env

from data.util import some
from data.coords import EarthCoords
from data.nav import NavpointError


# ---------- Constants ----------

fmt_dms = '(\\d{1,3})\\.(\\d{1,2})\\.(\\d{1,2})\\.(\\d{,3})'
re_point = re.compile('(?P<lat>[NSns]%s) +(?P<lon>[EWew]%s)|(?P<named>\\w+) +(?P=named)' % (fmt_dms, fmt_dms))

# -------------------------------


def bg_basename(file_key):
	return 'bg-%s-%s' % (settings.location_code, file_key)



def read_point(s):
	match = re_point.fullmatch(s)
	if match:
		if match.group('named') == None: # lat/lon coordinates in SCT format
			lat, lon = s.split()
			lat_d, lat_m, lat_s = lat[1:].split('.', maxsplit=2)
			lon_d, lon_m, lon_s = lon[1:].split('.', maxsplit=2)
			return EarthCoords.fromString('%sd%sm%ss%s,%sd%sm%ss%s' \
				% (lat_d, lat_m, lat_s, lat[0].upper(), lon_d, lon_m, lon_s, lon[0].upper()))
		else: # named point
			try:
				return env.navpoints.findUnique(match.group('named')).coordinates
			except NavpointError as err:
				raise ValueError('Named point out of range or not unique: %s' % s)
	else:
		raise ValueError('Not a valid point spec: %s' % s)


def get_segment(txt):
	tokens = txt.split(maxsplit=4)
	if len(tokens) < 4: # len should be 4 or 5
		raise ValueError('Missing tokens')
	p1 = read_point(' '.join(tokens[0:2]))
	p2 = read_point(' '.join(tokens[2:4]))
	return (p1, p2, tokens[:4]), (tokens[4] if len(tokens) > 4 else '')
	


def repl_spaces(txt, repl='_'):
	return re.sub(' ', repl, txt)


def point_to_string(p):
	if isinstance(p, EarthCoords):
		return p.toString()
	else: # named point
		return p




def extract_sector(sector_file, centre_point, range_limit):
	with open(settings.outputFileName('bg-extract', sessionID=False, ext='err'), 'w', encoding='utf8') as ferr:
		with open(sector_file, encoding='iso-8859-15') as fin:
			print('Extracting from sector file "%s"... ' % sector_file)
			in_section = last_file = last_drawing_block = last_coord_spec = None
			src_line_number = 0
			files = {} # file key -> file
			object_counters = {} # file name -> int
			for src_line in fin:
				src_line_number += 1
				line = src_line.split(';', maxsplit=1)[0].rstrip()
				
				# --- Interpret spec line --- #
				got_segment = None # if set below, must also set: output_file, drawing_block, block_colour
				
				if line == '':
					continue
				
				elif line.startswith('[') and line.endswith(']'):
					in_section = line[1:-1]
				
				# --------- GEO --------- #
				elif in_section == 'GEO':
					try:
						got_segment, drawing_block = get_segment(line)
						if drawing_block == '':
							drawing_block = 'unnamed'
						output_file = 'geo-' + repl_spaces(drawing_block)
						block_colour = 'yellow'
					except ValueError as err:
						ferr.write('Line %d: %s\n' % (src_line_number, err))
				
				# ---- ARTCC (HI/LO), SID, STAR ---- #
				elif in_section in ['SID', 'STAR'] or in_section != None and in_section.startswith('ARTCC'):
					if line.startswith(' '): # indented sequal to prev. line
						if last_drawing_block == None:
							ferr.write('Isolated %s segment on line %d; is header commented out?\n' % (in_section, src_line_number))
						else:
							drawing_block = last_drawing_block
							try:
								got_segment, rest_of_line = get_segment(line)
							except ValueError as err:
								ferr.write('Line %d: %s\n' % (src_line_number, err))
					else: # not on an indented line
						if in_section in ['SID', 'STAR']:
							drawing_block = line[:26].strip()
							try:
								got_segment, rest_of_line = get_segment(line[26:])
							except ValueError as err:
								ferr.write('Line %d: %s\n' % (src_line_number, err))
						else: # in an ARTCC section
							line_split = [s.strip() for s in line.split(' ', maxsplit=1)] # min len is 1
							drawing_block = line_split[0]
							try:
								got_segment, rest_of_line = get_segment(line_split[1])
							except IndexError:
								ferr.write('Missing point specifications on line %d\n' % src_line_number)
							except ValueError as err:
								ferr.write('Line %d: %s\n' % (src_line_number, err))
					
					if got_segment: # still on boundary or proc section line
						if in_section in ['SID', 'STAR']:
							output_file = 'proc-%s' % in_section
							block_colour = {'SID':'#%02X%02XFF', 'STAR':'#FF%02X%02X'}[in_section] % (randint(0, 0xDD), randint(0, 0xDD))
						else: # ARTCC
							output_file = 'boundaries-%s' % {'ARTCC': 'main', 'ARTCC HIGH': 'high', 'ARTCC LOW': 'low'}.get(in_section, 'unknown')
							block_colour = 'cyan'
					
				# ---- Write if necessary ---- #
				# must set: last_output_file, last_drawing_block, last_coord_spec
				
				if got_segment:
					point1, point2, coords_spec = got_segment
				if got_segment and all(p.distanceTo(centre_point) <= range_limit for p in (point1, point2)):
					try:
						fout = files[output_file]
					except KeyError:
						new_file = settings.outputFileName(bg_basename(output_file), sessionID=False, ext='extract')
						fout = files[output_file] = open(new_file, 'w', encoding='utf8')
						object_counters[output_file] = 0
					if output_file == last_output_file and drawing_block == last_drawing_block \
								and coords_spec[0] == last_coord_spec[0] and coords_spec[1] == last_coord_spec[1]:
						fout.write('%s\n' % point_to_string(point2))
					else:
						fout.write('\n%s\n' % block_colour)
						fout.write('%s  %s @%d\n' % (point_to_string(point1), drawing_block, src_line_number))
						fout.write('%s\n' % point_to_string(point2))
						object_counters[output_file] += 1
					last_output_file = output_file
					last_drawing_block = drawing_block
					last_coord_spec = coords_spec[2:4]
				else:
					last_output_file = last_drawing_block = last_coord_spec = None
	extract_lst_file = settings.outputFileName('%s.lst' % settings.location_code, sessionID=False, ext='extract')
	with open(extract_lst_file, 'w', encoding='utf8') as flst:
		for fkey in sorted(files):
			flst.write('%s\tDRAW\t%s: %d object(s)\n' % (bg_basename(fkey), fkey, object_counters[fkey]))
			files[fkey].close()
	print('Wrote ".lst" menu and %d background drawing file(s).' % len(files))



