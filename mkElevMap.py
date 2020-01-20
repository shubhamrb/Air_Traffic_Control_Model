

import sys
from subprocess import Popen, PIPE

from data.coords import EarthCoords, RadarCoords, m2NM, m2ft
from data.elev import ElevationMap


# ---------- Constants ----------

output_file = 'output/auto.elev'
default_fgelev_cmd = 'fgelev' # no default options

# -------------------------------


if __name__ == "__main__":
	args = sys.argv[1:]
	if len(args) != 3 and not (len(args) >= 5 and args[3] == '--'):
		sys.exit('Usage: %s <nw> <se> <prec_metres> [-- <fgelev_cmd>]' % sys.argv[0])
	nw = EarthCoords.fromString(args[0])
	se = EarthCoords.fromString(args[1])
	prec_NM = m2NM * float(args[2])
	fgelev_cmd = default_fgelev_cmd if len(args) < 5 else args[4]
	fgelev_opts = args[5:]
	
	EarthCoords.setRadarPos(nw)
	rnw = nw.toRadarCoords() # 0,0
	rse = se.toRadarCoords() # lon_diff_NM, lat_diff_NM
	lon_diff_NM = rse.x()
	lat_diff_NM = rse.y()
	n_rows = int(lat_diff_NM / prec_NM + .5) + 1
	n_cols = int(lon_diff_NM / prec_NM + .5) + 1
	elev = ElevationMap(rnw, rse, n_rows, n_cols) # checks dimensions and creates store table
	print('Map has %d rows and %d columns.' % (n_rows, n_cols))
	
	with Popen([fgelev_cmd] + fgelev_opts, stdin=PIPE, stdout=PIPE, bufsize=1, universal_newlines=True) as fgelev:
		print('Reading elevations...')
		count = 0
		for i in range(n_rows):
			for j in range(n_cols):
				print('%d%%' % (100 * count / n_rows / n_cols), end='\r')
				coords = EarthCoords.fromRadarCoords(RadarCoords(j * lon_diff_NM / (n_cols - 1), i * lat_diff_NM / (n_rows - 1)))
				print('%d,%d %f %f' % (i, j, coords.lon, coords.lat), file=fgelev.stdin)
				line = fgelev.stdout.readline()
				ok = False
				tokens = [tok.strip() for tok in line.split(':')]
				if len(tokens) == 2:
					row, col = (int(tok) for tok in tokens[0].split(','))
					if row == i and col == j:
						elev.setElevation(int(row), int(col), m2ft * float(tokens[1]))
						ok = True
				if not ok:
					print('Unexpected response from fgelev for row/col %d,%d: %s' % (i, j, line.encode('utf8')))
				count += 1
		print('Done.')
	
	with open(output_file, 'w', encoding='utf8') as fout:
		fout.write('#\n')
		fout.write('# Elevation map generated with mkElevMap.py script\n')
		fout.write('#\n\n')
		fout.write('%s  %s\n' % (nw.toString(), se.toString()))
		elev.printElevations(f=fout, indent=True)
	
	print('Created file: %s' % output_file)

