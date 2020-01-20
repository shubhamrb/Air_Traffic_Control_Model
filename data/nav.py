
from data.coords import EarthCoords
from data.util import A_star_search


# ---------- Constants ----------

# -------------------------------



class Navpoint:
	## STATIC:
	types = AD, VOR, NDB, FIX, ILS, RNAV = range(6)
	
	def tstr(t):
		return { \
			Navpoint.AD: 'AD', \
			Navpoint.VOR: 'VOR', \
			Navpoint.NDB: 'NDB', \
			Navpoint.FIX: 'Fix', \
			Navpoint.ILS: 'ILS', \
			Navpoint.RNAV: 'RNAV'
		}[t]
	
	def findType(typestr):
		try:
			return { \
				'AD': Navpoint.AD, \
				'VOR': Navpoint.VOR, \
				'NDB': Navpoint.NDB, \
				'FIX': Navpoint.FIX, \
				'ILS': Navpoint.ILS, \
				'RNAV': Navpoint.RNAV
			}[typestr.upper()]
		except KeyError:
			raise ValueError('Invalid navpoint type specifier "%s"' % typestr)
	
	def __init__(self, t, code, coords):
		'''
		code should be upper case
		'''
		self.type = t
		self.code = code
		self.coordinates = coords
		self.long_name = '' # to be overridden if applicable
	
	def __str__(self):
		return self.code
	




class Airfield(Navpoint):
	def __init__(self, icao, coords, airport_name):
		Navpoint.__init__(self, Navpoint.AD, icao, coords)
		self.long_name = airport_name


class VOR(Navpoint):
	def __init__(self, identifier, coords, frq, long_name, tacan=False):
		Navpoint.__init__(self, Navpoint.VOR, identifier, coords)
		self.long_name = long_name
		self.frequency = frq
		self.dme = False
		self.tacan = tacan


class NDB(Navpoint):
	def __init__(self, identifier, coords, frq, long_name):
		Navpoint.__init__(self, Navpoint.NDB, identifier, coords)
		self.long_name = long_name
		self.frequency = frq
		self.dme = False


class Fix(Navpoint):
	def __init__(self, name, coords):
		Navpoint.__init__(self, Navpoint.FIX, name, coords)


class Rnav(Navpoint):
	def __init__(self, name, coords):
		Navpoint.__init__(self, Navpoint.RNAV, name, coords)














class NavpointError(Exception):
	pass








class NavDB:
	def __init__(self):
		self.by_type = { t:[] for t in Navpoint.types } # type -> navpoint list (KeyError safe)
		self.by_code = {} # code -> navpoint list (KeyError is possible)
	
	def add(self, p):
		self.by_type[p.type].append(p)
		try:
			self.by_code[p.code].append(p)
		except KeyError:
			self.by_code[p.code] = [p]
	
	def clear(self):
		for key in self.by_type:
			self.by_type[key] = []
		self.by_code.clear()
	
	def byType(self, t): # WARNING: do not alter result
		return self.by_type[t]
	
	def findAll(self, code=None, types=Navpoint.types): # WARNING: do not alter result
		if code == None:
			result = []
			for t in types:
				result += self.byType(t)
			return result
		else:
			key = code.upper()
			return [p for p in self.by_code.get(key, []) if p.type in types]
	
	def findUnique(self, code, types=Navpoint.types):
		'''
		raises NavpointError if zero or more than one navpoint is found with given code and whose type is in "types" list
		'''
		candidates = self.findAll(code, types)
		if len(candidates) != 1:
			raise NavpointError(str(code) if code != None else '')
		return candidates[0]
	
	def findClosest(self, ref, code=None, types=Navpoint.types, maxDist=None):
		'''
		raises NavpointError if no navpoint is found with given code and type in "types" list
		'''
		candidates = self.findAll(code, types)
		if len(candidates) > 0:
			closest = min(candidates, key=(lambda p: ref.distanceTo(p.coordinates)))
			if maxDist == None or closest.coordinates.distanceTo(ref) <= maxDist:
				return closest
		raise NavpointError(str(code) if code != None else '')
	
	def findAirfield(self, icao):
		'''
		raises ValueError if None is given as argument
		raises NavpointError if no airfield is found with given code
		'''
		if icao == None:
			raise ValueError('NavDB.findAirfield: no airport given')
		return self.findUnique(icao, types=[Navpoint.AD]) # can raise NavpointError
	
	def subDB(self, pred):
		result = NavDB()
		result.by_type = { t: [p for p in plst if pred(p)] for t, plst in self.by_type.items() }
		result.by_code = { c: [p for p in plst if pred(p)] for c, plst in self.by_code.items() if plst != [] }
		return result




world_navpoint_db = NavDB()








class RoutingDB:
	def __init__(self):
		self.airways = {} # navpoint -> (navpoint -> (str name, int FL_min, int FL_max))
		self.entries = {} # str ICAO code -> (navpoint, str list leg spec) list
		self.exits = {}   # str ICAO code -> (navpoint, str list leg spec) list
	
	
	## POPULATE/CLEAR
	
	def addAwy(self, p1, p2, name, fl_lo, fl_hi):
		try:
			self.airways[p1][p2] = name, fl_lo, fl_hi # may override an adge if already one between those two points
		except KeyError:
			self.airways[p1] = { p2: (name, fl_lo, fl_hi) }
	
	def addEntryPoint(self, ad, p, leg_spec):
		try:
			self.entries[ad.code].append((p, leg_spec))
		except KeyError:
			self.entries[ad.code] = [(p, leg_spec)]
	
	def addExitPoint(self, ad, p, leg_spec):
		try:
			self.exits[ad.code].append((p, leg_spec))
		except KeyError:
			self.exits[ad.code] = [(p, leg_spec)]
	
	def clearEntryExitPoints(self):
		self.entries.clear()
		self.exits.clear()
	
	
	## ACCESS
	
	def airfieldsWithEntryPoints(self):
		return [world_navpoint_db.findAirfield(icao) for icao in self.entries]
	
	def airfieldsWithExitPoints(self):
		return [world_navpoint_db.findAirfield(icao) for icao in self.exits]
	
	def entriesTo(self, ad):
		return self.entries.get(ad.code, [])
	
	def exitsFrom(self, ad):
		return self.exits.get(ad.code, [])
	
	
	## ROUTING
	
	def _waypointsFrom(self, p1, destination):
		try: # FUTURE depend on a current FL for AWYs (or at least a hi/lo layer)?
			res = [(p2, p1.coordinates.distanceTo(p2.coordinates), awy[0]) for p2, awy in self.airways[p1].items()]
		except KeyError:
			res = []
		if p1.type == Navpoint.AD:
			res.extend((p2, p1.coordinates.distanceTo(p2.coordinates), ' '.join(legspec)) for p2, legspec in self.exitsFrom(p1))
		for entry_point, legspec in self.entriesTo(destination):
			if p1 == entry_point:
				res.append((destination, p1.coordinates.distanceTo(destination.coordinates), ' '.join(legspec)))
		return res
	
	def shortestRoute(self, p1, p2):
		'''
		returns a PAIR of lists: waypoint hops, AWY legs
		result is the shortest route in distance using AWYs, with no intermediate waypoints along AWYs
		p1 and p2 can be any Navpoint; raises ValueError if no route exists
		'''
		fh = lambda p: p.coordinates.distanceTo(p2.coordinates)
		waypoints, awys = A_star_search(p1, p2, (lambda p: self._waypointsFrom(p, p2)), heuristic=fh) # may raise ValueError
		# Simplify lists: remove waypoints when remaining on same AWY
		i = 0
		while i < len(waypoints) - 1:
			if awys[i] == awys[i + 1]:
				del awys[i]
				del waypoints[i]
			else:
				i += 1
		return waypoints, awys
	
	def shortestRouteStr(self, p1, p2):
		'''
		returns a string spec of the shortest route, without p1 and p2
		raises ValueError if no route exists
		'''
		waypoints, awys = self.shortestRoute(p1, p2) # may raise ValueError
		if len(waypoints) == 0:
			return ''
		else:
			pairs = list(zip(waypoints, awys))
			s = ' '.join('%s %s' % (awy, wp) for wp, awy in pairs[:-1]) + ' ' + awys[-1]
			return s.strip()




world_routing_db = RoutingDB()

