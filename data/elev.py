
import sys
from math import floor


# ---------- Constants ----------

# -------------------------------


class ElevationMap:
	def __init__(self, nw, se, nrows, ncols):
		# corners are RadarCoords (avoids edges)
		# both dimensions must be >= 2, and equal to the number of values wanted between the two limits (included)
		if nw.x() >= se.x() or nw.y() >= se.y():
			raise ValueError('bad corners')
		elif nrows < 2 or ncols < 2:
			raise ValueError('insufficient precision (more values needed)')
		self.map = [[0 for col in range(ncols)] for row in range(nrows)] # access is map[row][col]
		# Linear functions for continuous indices in [0, max_index]
		# fj(x) = aj*x + bj, fj(west) = 0, fj(east) = ncols
		self.aj = (ncols - 1) / (se.x() - nw.x())
		self.bj = -self.aj * nw.x()
		# fi(y) = ai*y + bi, fi(north) = 0, fi(south) = nrows
		self.ai = (nrows - 1) / (se.y() - nw.y())
		self.bi = -self.ai * nw.y()
	
	def setElevation(self, i, j, elevation):
		self.map[i][j] = elevation
	
	def elev(self, coords):
		x = self.aj * coords.x() + self.bj
		y = self.ai * coords.y() + self.bi
		i = floor(y) # row in map matrix
		j = floor(x) # column in map matrix
		if not (0 <= i < len(self.map) - 1 and 0 <= j < len(self.map[0]) - 1):
			raise ValueError('bad indices for height map (%d, %d)' % (i, j))
		h11 = self.map[i][j]
		h12 = self.map[i+1][j]
		h21 = self.map[i][j+1]
		h22 = self.map[i+1][j+1]
		dfx = h21 - h11
		dfy = h12 - h11
		dfxy = h11 + h22 - h21 - h12
		xoff = x - j
		yoff = y - i
		return dfx * xoff + dfy * yoff + dfxy * xoff * yoff + h11
	
	def printElevations(self, f=sys.stdout, indent=False):
		for i, row in enumerate(self.map):
			print(int(indent) * '\t' + '\t'.join(str(v) for v in row), file=f)
		


