from datetime import timedelta

from data.util import pop_all, A_star_search

from data.coords import m2NM
from data.db import acft_cat
from data.utc import now


# ---------- Constants ----------

default_RWY_disp_line_length = 25 # NM
default_RWY_FPA = 5.2 # percent

max_twy_edge_length = .1 # NM
inserted_twy_node_prefix = 'ADDED:'

straight_taxi_max_turn = 20 # degrees
max_rwy_turn_off_angle = 90 # degrees

# -------------------------------




class AirportData:
	def __init__(self):
		self.navpoint = None
		self.physical_runways = [] # list of (dirRWY 1, dirRWY 2, float width in metres, surface type X-plane code) tuples
		self.directional_runways = {} # str -> DirRunway dict
		self.helipads = []  # Helipad list
		self.ground_net = None
		self.field_elevation = None
		self.viewpoints = [] # apt.dat specified viewpoints (tower)
		self.windsocks = []  # coordinates
		self.transition_altitude = None
		# ATTRIBUTE BELOW: list items match indices in self.physical_runways
		self.physical_RWY_box_WTC_timer = [] # time+WTC when physical runway strip box freed (manually reset)
	
	def addPhysicalRunway(self, width, surface, rwy1, rwy2):
		rwy1._opposite_runway = rwy2
		rwy2._opposite_runway = rwy1
		rwy1._orientation = rwy1.thr.headingTo(rwy2.thr)
		rwy2._orientation = rwy2.thr.headingTo(rwy1.thr)
		rwy1._physical_runway = rwy2._physical_runway = len(self.physical_runways)
		rwy = min(rwy1, rwy2, key=(lambda r: r.name))
		self.physical_runways.append((rwy, rwy.opposite(), width, surface))
		self.physical_RWY_box_WTC_timer.append((now() - timedelta(days=1), None))
		self.directional_runways[rwy1.name] = rwy1
		self.directional_runways[rwy2.name] = rwy2
	
	def runway(self, rwy):
		return self.directional_runways[rwy]
	
	def runwayNames(self):
		return list(self.directional_runways.keys())
	
	def allRunways(self, sortByName=False):
		lst = list(self.directional_runways.values())
		if sortByName:
			lst.sort(key=(lambda r: r.name))
		return lst
	
	def physicalRunwayCount(self):
		return len(self.physical_runways)
	
	def physicalRunway(self, index):
		rwy1, rwy2, w, s = self.physical_runways[index]
		return rwy1, rwy2
	
	def physicalRunwayData(self, index):
		rwy1, rwy2, w, s = self.physical_runways[index]
		return w, s
	
	def physicalRunwayNameFromUse(self, index):
		rwy1, rwy2, w, s = self.physical_runways[index]
		if rwy1.inUse() == rwy2.inUse():
			return '%s/%s' % (rwy1.name, rwy2.name)
		else:
			return rwy1.name if rwy1.inUse() else rwy2.name
	
	def physicalRunwayWtcTimer(self, phyrwy_index):
		t, wtc = self.physical_RWY_box_WTC_timer[phyrwy_index]
		return now() - t, wtc
	
	def physicalRunway_restartWtcTimer(self, phyrwy_index, wtc):
		self.physical_RWY_box_WTC_timer[phyrwy_index] = now(), wtc






class DirRunway:
	def __init__(self, name, rwy_start, disp_thr):
		self.name = name # str
		self.thr = rwy_start # EarthCoords
		self.dthr = disp_thr # float metres
		# Changeable parameters
		self.use_for_departures = False
		self.use_for_arrivals = False
		# ILS properties
		self.ILS_cat = None     # or None if no LOC
		self.LOC_freq = None    # or None if no LOC
		self.LOC_range = None   # or None if no LOC
		self.LOC_bearing = None # or None if no LOC
		self.GS_range = None    # or None if no GS
		self.IM_pos = None      # or None
		self.MM_pos = None      # or None
		self.OM_pos = None      # or None
		# Saved parameters
		self.param_FPA = default_RWY_FPA # this is GS angle if ILS, or manually set (%)
		self.param_disp_line_length = default_RWY_disp_line_length
		self.param_acceptProps = True
		self.param_acceptTurboprops = True
		self.param_acceptJets = True
		self.param_acceptHeavy = True
	
	def physicalRwyIndex(self):
		return self._physical_runway
	
	def orientation(self):
		return self._orientation
	
	def opposite(self):
		return self._opposite_runway
	
	def threshold(self, dthr=False):
		if dthr:
			return self.thr.moved(self.orientation(), m2NM * self.dthr)
		else:
			return self.thr
	
	def length(self, dthr=False):
		return self.threshold(dthr=dthr).distanceTo(self.opposite().threshold(dthr=False))
	
	def inUse(self):
		return self.use_for_departures or self.use_for_arrivals
	
	def hasILS(self):
		return self.LOC_range != None and self.GS_range != None
	
	def appCourse(self):
		return self.orientation() if self.LOC_bearing == None else self.LOC_bearing
	
	def acceptsAcftType(self, t):
		'''
		NOTE: returns False if the X-plane category is unknown for the given ICAO type
		'''
		cat = acft_cat(t)
		return {
				'props': self.param_acceptProps, 'turboprops': self.param_acceptTurboprops, \
				'jets': self.param_acceptJets, 'heavy': self.param_acceptHeavy
			}.get(cat, False)



class Helipad:
	def __init__(self, name, centre, surface, length, width, ori):
		self.name = name # str
		self.centre = centre # EarthCoords
		self.surface = surface # bool
		self.length = length
		self.width = width
		self.orientation = ori
		










class GroundNetwork:
	'''
	Contains all nodes of ground nets, including those on runways and apron.
	An edge is considered on apron if the taxiway name connecting its two end nodes is None.
	'''
	def __init__(self):
		self._nodes = {} # node ID (str) -> EarthCoords
		self._neighbours = {} # node ID (str) -> (node ID (neighbour) -> taxiway name or None, str RWY spec or None, float length)
		self._pkpos = {} # pk ID (str) -> EarthCoords, Heading, str (gate|hangar|tie-down), cat list or [] for all
		self._twy_edges = {} # TWY -> node pair set # EDGES IN MOVEMENT AREA (controlled) OTHER THAN RUNWAYS
		self._apron_edges = set() # node pair set   # EDGES IN NON MOVEMENT AREA (ramp/apron)
		self.inserted_twy_node_counter = 0 # increments to generate new name for every inserted node (used to avoid too long edges)
	
	# BUILDERS
	def addNode(self, node, position):
		self._nodes[node] = position
		self._neighbours[node] = {}
	
	def addEdge(self, n1, n2, rwy, twy):
		'''
		Add an edge to the ground net.
		Specify rwy/twy:
		- none = apron edge (non-moving area)
		- RWY only = runway edge (on runway), give a str spec of which RWY the edge is on (usually bidir RWY/OPP format)
		- TWY only = taxiway edge (in moving area), give the name of the TWY the edge is part of
		- both: is invalid
		'''
		p1 = self.nodePosition(n1)
		p2 = self.nodePosition(n2)
		edge_length = p1.distanceTo(p2)
		if edge_length > max_twy_edge_length:
			new_node = inserted_twy_node_prefix + str(self.inserted_twy_node_counter)
			self.inserted_twy_node_counter += 1
			self.addNode(new_node, p1.moved(p1.headingTo(p2), edge_length / 2))
			self.addEdge(n1, new_node, rwy, twy)
			self.addEdge(new_node, n2, rwy, twy)
		else:
			self._neighbours[n1][n2] = self._neighbours[n2][n1] = twy, rwy, edge_length
			if twy == None:
				if rwy == None:
					self._apron_edges.add((n1, n2))
			else:
				try:
					self._twy_edges[twy].add((n1, n2))
				except KeyError:
					self._twy_edges[twy] = { (n1, n2) }
	
	def addParkingPosition(self, pkid, pos, hdg, typ, who):
		self._pkpos[pkid] = pos, hdg, typ, who
	
	# ACCESS NODES
	def nodes(self, filter=None):
		return list(self._nodes) if filter == None else [n for n in self._nodes if filter(n)]
	
	def nodePosition(self, nid):
		return self._nodes[nid]
	
	def neighbours(self, nid, twy=None, ignoreApron=False):
		ok = lambda t, r, l: (twy == None or t == twy) and not (ignoreApron and t == r == None)
		return [n for n, data in self._neighbours[nid].items() if ok(*data)]
	
	def nodeIsOnRunway(self, nid, rwy):
		return rwy in self.connectedRunways(nid, bidir=True)
	
	def connectedRunways(self, nid, bidir=False):
		res = set()
		for n2 in self.neighbours(nid):
			rwy_spec = self._neighbours[nid][n2][1]
			if rwy_spec != None:
				rwys = rwy_spec.split('/')
				if bidir:
					res.update(rwys)
				else:
					res.add(sorted(rwys)[0])
		return list(res)
	
	def closestNode(self, pos, maxdist=None):
		ndlst = [(n, self.nodePosition(n).distanceTo(pos)) for n in self._nodes]
		if ndlst != []:
			node, dist = min(ndlst, key=(lambda nd: nd[1]))
			if maxdist == None or dist <= maxdist:
				return node
		return None
	
	# ACCESS EDGES AND TAXIWAYS
	def taxiways(self):
		return list(self._twy_edges)
	
	def connectedTaxiways(self, nid):
		return [twy for twy, rwy, l in self._neighbours[nid].values() if twy != None]
	
	def apronEdges(self):
		return self._apron_edges
	
	def taxiwayEdges(self, twy):
		return self._twy_edges[twy]
	
	# ACCESS PARKING POSITIONS
	def parkingPositions(self, acftCat=None, acftType=None):
		if acftType == None and acftCat == None: # no ACFT type filter
			return list(self._pkpos)
		if acftType != None:
			assert acftCat == None
			acftCat = acft_cat(acftType) # may be None but OK
		return [pk for pk, pkinfo in self._pkpos.items() if acftCat in pkinfo[3] or pkinfo[3] == []]
	
	def parkingPosition(self, pkid):
		return self._pkpos[pkid][0]
	
	def parkingPosInfo(self, pkid):
		return self._pkpos[pkid]
	
	def closestParkingPosition(self, pos, maxdist=None):
		pklst = [(pk, self.parkingPosition(pk).distanceTo(pos)) for pk in self.parkingPositions()]
		if pklst != []:
			pk, dist = min(pklst, key=(lambda pk: pk[1]))
			if maxdist == None or dist <= maxdist:
				return pk
		return None
	
	# TURN-OFF POINTS
	def runwayTurnOffs(self, rwy, maxangle=90, minroll=0):
		'''
		Returns a list tuple (L1, L2, L3, L4) containing turn-offs after a landing roll down the given RWY, in preferred order:
		- L1 is the list of preferred turn-offs, i.e. respecting maximum turn-off angle and ending off all runways
		- L2 is the list of sharper turn-offs down the runway and ending on taxiways
		- L3 is the list of turn-offs requiring a backtrack
		- L4 is the list of turn-offs ending on a runway
		In all cases a turn-off is a tuple (n1, n2, d, a) where:
		- n1 is the turn-off node on the runway
		- n2 is the arrival node where the runway is cleared
		- d is the distance from threshold to n1
		- a is the turn angle, between runway and (n1, n2) heading
		All lists are sorted by distance from current point.
		'''
		res = []
		for rwy_node in self.nodes(lambda n: self.nodeIsOnRunway(n, rwy.name)):
			for n in self.neighbours(rwy_node):
				if not self.nodeIsOnRunway(n, rwy.name):
					rwy_point = self.nodePosition(rwy_node)
					thr_dist = rwy.threshold().distanceTo(rwy_point)
					turn_angle = rwy_point.headingTo(self.nodePosition(n)).diff(rwy.orientation())
					res.append((rwy_node, n, thr_dist, turn_angle))
		res.sort(key=(lambda t: t[2])) # sort by distance to THR
		res_worst = pop_all(res, lambda t: len(self.connectedRunways(t[1])) > 0) # turn off on a RWY
		res_worse = [(n1, n2, d, (a + 180) % 360) for n1, n2, d, a in pop_all(res, lambda t: t[2] < minroll)] # need backtrack
		res_worse.reverse()
		res_bad = pop_all(res, lambda t: abs(t[3]) > max_rwy_turn_off_angle) # sharp turn-off
		return res, res_bad, res_worse, res_worst
	
	# ROUTES
	def _routeHopsFrom(self, n1, avoid_runways):
		res = []
		for n2, (twy, rwy, cost) in self._neighbours[n1].items():
			if avoid_runways: # add penalties for entering/crossing RWYs
				if not all(self.nodeIsOnRunway(n1, r) for r in self.connectedRunways(n2)): # stepping on a RWY
					cost += 15
				elif rwy != None: # taxi edge fully on RWY
					cost += 5
			res.append((n2, cost, (twy, rwy))) # edge labels not used anyway
		return res
	
	def shortestTaxiRoute(self, src, goal, avoid_runways):
		fh = lambda n, g=self.nodePosition(goal): self.nodePosition(n).distanceTo(g)
		return A_star_search(src, goal, (lambda n: self._routeHopsFrom(n, avoid_runways)), heuristic=fh)[0]
	
	def taxiInstrStr(self, node_sequence, final_non_node=None):
		if node_sequence == []:
			if final_non_node == None:
				return 'Hold position'
			else:
				return 'Taxi to %s' % final_non_node
		elif len(node_sequence) == 1 and final_non_node == None:
			n = node_sequence[0]
			rwys = self.connectedRunways(n)
			if rwys == []:
				twys = self.connectedTaxiways(n)
				return 'Taxi on %s' % ('apron' if twys == [] else twys[0])
			else:
				return 'Enter RWY %s' % rwys[0]
		else:
			instr = []
			n_prev = node_sequence[0]
			edge_prev = None
			hdg_prev = None
			rwys_prev = self.connectedRunways(n_prev) if n_prev in self._nodes else []
			on_prev = []
			for n in node_sequence[1:]:
				twy_lbl, rwy_lbl, ignore_len = self._neighbours[n_prev][n] # n_prev is Not a pkpos (parking comes last)
				if twy_lbl == None and rwy_lbl == None:
					edge_lbl = 'apron'
				else:
					edge_lbl = 'RWY' + rwy_lbl if twy_lbl == None else twy_lbl
				hdg = self.nodePosition(n_prev).headingTo(self.nodePosition(n))
				turn = None if hdg_prev == None else hdg.diff(hdg_prev)
				rwys = self.connectedRunways(n)
				for r in on_prev:
					if r in [r for r in rwys_prev if r not in rwys]:
						instr.append('cross RWY %s' % r)
				if edge_lbl != edge_prev: # else: staying on same TWY => silent hop
					if turn == None:
						tt = 'Taxi' if instr == [] else 'then'
					elif abs(turn) <= straight_taxi_max_turn:
						tt = 'straight'
					else:
						tt = 'right' if turn > 0 else 'left'
					instr.append('%s on %s' % (tt, edge_lbl))
				edge_prev = edge_lbl
				on_prev = [r for r in rwys if r not in rwys_prev]
				n_prev = n
				hdg_prev = hdg
				rwys_prev = rwys
			if final_non_node != None: # recognise "to point"
				instr.append('%s to %s' % (('Taxi' if instr == [] else 'then'), final_non_node))
			if on_prev != []:
				instr.append('enter RWY %s' % on_prev[0])
			return ', '.join(instr)




