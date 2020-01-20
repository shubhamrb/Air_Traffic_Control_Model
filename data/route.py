from data.nav import world_navpoint_db, Airfield, NavpointError


# ---------- Constants ----------

route_acceptable_WPdistToArr_increase = 100 # NM

# -------------------------------



def airfield(a):
	return a if isinstance(a, Airfield) else world_navpoint_db.findAirfield(a)




class Route:
	def __init__(self, dep, arr, init_string):
		'''
		raises ValueError if 'dep' or 'arr' is an invalid airfield
		'''
		self.dep = airfield(dep)
		self.arr = airfield(arr)
		self.enroute_waypoints = [] # recognised navigation points in init_string
		self.leg_specs = [[]] # list of leg specs; each leg spec is a list of tokens
		init_tokens = init_string.split()
		prev = self.dep
		for token in init_tokens:
			try:
				next_waypoint = world_navpoint_db.findClosest(prev.coordinates, code=token)
				dist_limit = prev.coordinates.distanceTo(self.arr.coordinates) + route_acceptable_WPdistToArr_increase
				is_wp = next_waypoint.coordinates.distanceTo(self.arr.coordinates) <= dist_limit
			except NavpointError:
				is_wp = False
			if is_wp:
				self.enroute_waypoints.append(next_waypoint)
				self.leg_specs.append([])
				prev = next_waypoint
			else:
				self.leg_specs[-1].append(token)
		# Remove duplicated end airfields if no leg specs
		if self.enroute_waypoints !=[] and self.enroute_waypoints[0] is self.dep and self.leg_specs[0] == []:
			del self.enroute_waypoints[0]
			del self.leg_specs[0]
		if self.enroute_waypoints !=[] and self.enroute_waypoints[-1] is self.arr and self.leg_specs[-1] == []:
			del self.enroute_waypoints[-1]
			del self.leg_specs[-1]
	
	def dup(self):
		dup = Route(self.dep, self.arr, '')
		dup.enroute_waypoints = self.enroute_waypoints[:]
		dup.leg_specs = self.leg_specs[:]
		return dup
	
	
	## ACCESS
	
	def legCount(self):
		return len(self.leg_specs)
	
	def waypoint(self, n):
		'''
		waypoint 0 is the first waypoint after departure
		'''
		return self.enroute_waypoints[n] if n < self.legCount() - 1 else self.arr
	
	def legSpec(self, n):
		'''
		this method returns the leg spec tokens of the leg to waypoint 'n' (n=0 is departure leg)
		'''
		return self.leg_specs[n]
	
	
	## TESTS
	
	def __contains__(self, navpoint):
		'''
		tests if navpoint is an enroute waypoint (this excludes departure and arrival points)
		'''
		try:
			ignore = next(wp for wp in self.enroute_waypoints if wp is navpoint)
			return True
		except StopIteration:
			return False
	
	
	## METHODS
	
	def routePoints(self):
		return [self.dep] + [self.waypoint(i) for i in range(self.legCount())]
	
	def totalDistance(self):
		result = self.dep.coordinates.distanceTo(self.waypoint(0).coordinates)
		for i in range(self.legCount() - 1):
			result += self.waypoint(i).coordinates.distanceTo(self.waypoint(i + 1).coordinates)
		return result
	
	def currentLegIndex(self, position):
		'''
		returns the number of the route leg to be followed, based on distance to arrival, given a position on Earth
		0 is first; legCount-1 is last
		'''
		dist_to_dep = position.distanceTo(self.dep.coordinates)
		dist_to_arr = position.distanceTo(self.arr.coordinates)
		if dist_to_dep < dist_to_arr and dist_to_dep < self.dep.coordinates.distanceTo(self.waypoint(0).coordinates):
			return 0
		for i in reversed(range(self.legCount() - 1)):
			if self.waypoint(i).coordinates.distanceTo(self.arr.coordinates) >= dist_to_arr:
				return i + 1
		return 0
	
	def currentWaypoint(self, position):
		return self.waypoint(self.currentLegIndex(position))
	
	def SID(self):
		if self.legCount() > 1 and 'SID' in [token.upper() for token in self.legSpec(0)]:
			return str(self.waypoint(0))
		else:
			return None
	
	def STAR(self):
		if self.legCount() > 1 and 'STAR' in [token.upper() for token in self.legSpec(self.legCount() - 1)]:
			return str(self.waypoint(self.legCount() - 2))
		else:
			return None
	
	
	## STRINGS
	
	def __str__(self):
		return '%s %s' % (self.dep, ' '.join(self.legStr(i, start=False) for i in range(self.legCount())))
	
	def enRouteStr(self):
		result = ' '.join(self.legStr(i, start=False) for i in range(self.legCount() - 1))
		last_leg_spec = ' '.join(self.legSpec(self.legCount() - 1))
		if last_leg_spec != '':
			result += ' ' + last_leg_spec
		return result
	
	def legStr(self, n, start=True):
		leg_start = str(self.dep if n == 0 else self.waypoint(n - 1)) + ' ' if start else ''
		leg_specs = ' '.join(self.legSpec(n))
		if leg_specs != '':
			leg_specs += ' '
		return leg_start + leg_specs + str(self.waypoint(n))
	
	def toGoStr(self, position):
		ileg = self.currentLegIndex(position)
		start = '%s ' % self.dep if ileg == 0 else '... %s ' % self.waypoint(ileg - 1)
		return start + ' '.join(self.legStr(i, start=False) for i in range(ileg, self.legCount()))
	
	
	## MODIFIERS
	
	def removeWaypoint(self, navpoint):
		'''
		returns the lost leg specs (before wp, after wp)
		'''
		leg = next(ileg for ileg in reversed(range(self.legCount() - 1)) if self.waypoint(ileg) is navpoint)
		del self.enroute_waypoints[leg]
		lost_before = self.leg_specs.pop(leg)
		lost_after = self.leg_specs.pop(leg)
		self.leg_specs.insert(leg, [])
		return lost_before, lost_after
	
	def insertWaypoint(self, navpoint):
		'''
		returns the lost leg spec
		'''
		leg = self.currentLegIndex(navpoint.coordinates)
		self.enroute_waypoints.insert(leg, navpoint)
		old_leg_spec = self.legSpec(leg)
		self.leg_specs[leg] = []
		self.leg_specs.insert(leg, [])
		return old_leg_spec

