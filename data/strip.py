
from datetime import datetime, timedelta, timezone

from session.config import settings

from data.util import some
from data.fpl import FPL
from data.nav import NavpointError
from data.params import Heading, StdPressureAlt, Speed
from data.route import Route


# ---------- Constants ----------

strip_mime_type = 'application/x-strip'
unfollowedRouteWarning_min_distToAD = 40

parsed_route_detail = 'parsed_route'	# Route
received_from_detail = 'fromATC'			# str (callsign)
sent_to_detail = 'toATC'							# str (callsign)
recycled_detail = 'recycled'					# bool
shelved_detail = 'shelved'						# bool
auto_printed_detail = 'auto_printed'  # bool
assigned_heading_detail = 'assHdg'		# Heading
assigned_altitude_detail = 'assAlt'		# str (reading in FL or ft AMSL)
assigned_speed_detail = 'assSpd'			# Speed
assigned_SQ_detail = 'assSQ'					# int (*OCTAL* code)
soft_link_detail = 'softlink'					# Aircraft (the identified radar contact)
rack_detail = 'rack' 									# str (or None if strip is unracked, i.e. loose or boxed)
runway_box_detail = 'rwybox'					# int (the physical RWY index in AD data, or None if strip is not boxed)
duplicate_callsign_detail = 'dupCS'		# bool (duplicate callsign detected)

strip_editable_FPL_details = [FPL.CALLSIGN, FPL.ACFT_TYPE, FPL.WTC, FPL.ICAO_DEP, FPL.ICAO_ARR, \
		FPL.CRUISE_ALT, FPL.TAS, FPL.FLIGHT_RULES, FPL.ROUTE, FPL.COMMENTS]
handover_details = list(FPL.details) + \
		[assigned_SQ_detail, assigned_heading_detail, assigned_altitude_detail, assigned_speed_detail]

# -------------------------------


class Strip:	
	def __init__(self):
		self.details = {} # strip can contain any string or FPL detail key values
		self.linked_aircraft = None
		self.linked_FPL = None
	
	def __str__(self):
		return '[%s:%s]' % (some(self.lookup(rack_detail), ''), some(self.callsign(), ''))
	
	def _parseRoute(self):
		try:
			dep = self.lookup(FPL.ICAO_DEP, fpl=True)
			arr = self.lookup(FPL.ICAO_ARR, fpl=True)
			mid = self.lookup(FPL.ROUTE, fpl=True)
			self.details[parsed_route_detail] = Route(some(dep, ''), some(arr, ''), some(mid, ''))
		except NavpointError: # One of the end airports is missing or unrecognised
			self.details[parsed_route_detail] = None
	
	
	## ENCODE/DECODE
	
	# double-backslash separates details (top-level separator)
	# backslash+n encodes new line
	# backslash+space encodes normal backslash

	def encodeDetails(self, details):
		unescaped_details = []
		for d in details:
			v = self.lookup(d)
			if v != None:
				try:
					unescaped_details.append('%s %s' % detail2str(d, v))
				except ValueError as err:
					print('ERROR: %s' % err)
		return r'\\'.join(dvstr.replace('\\', r'\ ').replace('\n', r'\n') for dvstr in unescaped_details)

	def fromEncodedDetails(encoded_details):
		strip = Strip()
		for encoded_detail in encoded_details.split(r'\\'):
			unescaped = encoded_detail.replace(r'\n', '\n').replace(r'\ ', '\\')
			tokens = unescaped.split(maxsplit=1)
			if len(tokens) == 0:
				continue # Ignore empty detail sections. Normally happens only if strip has no details at all.
			if len(tokens) == 1:
				tokens.append('')
			try:
				d, v = str2detail(tokens[0], tokens[1]) # may raise ValueError
				strip.writeDetail(d, v)
			except ValueError as err:
				print('ERROR: %s' % err)
		return strip
	
	
	## ACCESS
	
	def linkedFPL(self):
		return self.linked_FPL
	
	def linkedAircraft(self):
		return self.linked_aircraft
	
	def lookup(self, key, fpl=False):
		'''
		returns the value written on the strip. If None while 'fpl' is True: look up linked flight plan
		'''
		if key in self.details: # Strip has detail of its own
			return self.details[key]
		elif fpl and key in FPL.details and self.linkedFPL() != None:
			return self.linkedFPL()[key]
		return None
	
	def callsign(self, fpl=False, acft=False):
		assert not fpl or not acft
		res = self.lookup(FPL.CALLSIGN, fpl)
		if res == None and acft:
			la = self.linkedAircraft()
			if la != None:
				return la.xpdrCallsign()
		return res
	
	def assignedPressureAlt(self, qnh):
		'''
		returns the StdPressureAlt of the assigned_altitude_detail if valid
		returns None if None or invalid
		'''
		assAlt = self.lookup(assigned_altitude_detail) # str reading
		if assAlt == None:
			return None
		try:
			return StdPressureAlt.fromReading(assAlt, qnh)
		except ValueError:
			return None
	
	def FPLconflictList(self):
		'''
		what radar picks up that is different from flight plan information if any
		Returns: FPL detail list
		'''
		conflicts = []
		fpl = self.linkedFPL()
		if fpl != None:
			for d in FPL.details:
				got = self.lookup(d, fpl=False)
				if got != None and got != fpl[d]:
					conflicts.append(FPL.detailStrNames[d])
		return conflicts

	def transponderConflictList(self):
		'''
		what radar picks up that is different from strip information if any
		Returns a string list
		'''
		conflicts = []
		acft = self.linkedAircraft()
		if acft != None:
			if acft.xpdrCallsign() != None and self.callsign(fpl=True) != None and acft.xpdrCallsign().upper() != self.callsign(fpl=True).upper():
				conflicts.append(FPL.detailStrNames[FPL.CALLSIGN])
			if acft.xpdrAcftType() != None and self.lookup(FPL.ACFT_TYPE, fpl=True) != None \
					and acft.xpdrAcftType().upper() != self.lookup(FPL.ACFT_TYPE, fpl=True).upper():
				conflicts.append(FPL.detailStrNames[FPL.ACFT_TYPE])
			if acft.xpdrCode() != None and self.lookup(assigned_SQ_detail) != None and acft.xpdrCode() != self.lookup(assigned_SQ_detail):
				conflicts.append('SQ')
		return conflicts
	
	def vectoringConflicts(self, qnh):
		'''
		Returns a dict of (conflicting detail --> value diff) associations where conflict exceeds tolerance
		'''
		conflicts = {}
		acft = self.linkedAircraft()
		if acft != None and not acft.considerOnGround():
			curHdg = acft.heading()
			assHdg = self.lookup(assigned_heading_detail)
			if curHdg != None and assHdg != None:
				diff = curHdg.diff(assHdg, settings.heading_tolerance)
				if diff != 0:
					conflicts[assigned_heading_detail] = diff
			curAlt = acft.xpdrAlt()
			assAlt = self.assignedPressureAlt(qnh)
			if curAlt != None and assAlt != None:
				diff = curAlt.diff(assAlt, settings.altitude_tolerance)
				if diff != 0:
					conflicts[assigned_altitude_detail] = diff
			curIAS = acft.IAS()
			assIAS = self.lookup(assigned_speed_detail)
			if curIAS != None and assIAS != None:
				diff = curIAS.diff(assIAS, settings.speed_tolerance)
				if diff != 0:
					conflicts[assigned_speed_detail] = diff
		return conflicts
	
	def routeConflict(self):
		acft = self.linkedAircraft()
		route = self.lookup(parsed_route_detail)
		if acft == None or route == None or self.lookup(assigned_heading_detail) != None:
			return False
		else:
			pos = acft.coords()
			hdg = acft.heading()
			leg = route.currentLegIndex(pos)
			wp = route.waypoint(leg).coordinates
			return hdg != None \
				and not (leg == 0 and pos.distanceTo(route.dep.coordinates) < unfollowedRouteWarning_min_distToAD) \
				and not (leg == route.legCount() - 1 and pos.distanceTo(wp) < unfollowedRouteWarning_min_distToAD) \
				and hdg.diff(pos.headingTo(wp), settings.heading_tolerance) != 0
				
	
	## MODIFY
	
	def writeDetail(self, key, value):
		if value == None or value == '':
			if key in self.details:
				del self.details[key]
		else:
			self.details[key] = value
		if key in [FPL.ROUTE, FPL.ICAO_DEP, FPL.ICAO_ARR]:
			self._parseRoute()
	
	def linkFPL(self, fpl, autoFillOK=True):
		'''
		autoFillOK lets the method automatically write blank details on the strip,
		depending on auto-fill user setting (set autoFillOK=False to prevent)
		'''
		self.linked_FPL = fpl
		self._parseRoute()
		if autoFillOK and fpl != None and settings.strip_autofill_on_FPL_link:
			self.fillFromFPL()
	
	def linkAircraft(self, acft):
		self.linked_aircraft = acft
	
	def pushToFPL(self):
		fpl = self.linkedFPL()
		if fpl != None:
			for d, v in self.details.items():
				if d in FPL.details:
					fpl[d] = v
	
	def fillFromFPL(self, detail=None, ovr=False):
		fpl = self.linkedFPL()
		if fpl != None:
			details = [detail] if detail != None else strip_editable_FPL_details
			for detail in details:
				if fpl[detail] != None and (ovr or detail not in self.details):
					self.writeDetail(detail, fpl[detail])
	
	def fillFromXPDR(self, ovr=False):
		acft = self.linkedAircraft()
		if acft != None:
			details = { FPL.CALLSIGN: acft.xpdrCallsign(), FPL.ACFT_TYPE: acft.xpdrAcftType(), assigned_SQ_detail: acft.xpdrCode() }
			for detail, xpdr_value in details.items():
				if xpdr_value != None and (ovr or detail not in self.details):
					self.writeDetail(detail, xpdr_value)
	
	def clearVectors(self):
		for detail in [assigned_heading_detail, assigned_altitude_detail, assigned_speed_detail]:
			self.writeDetail(detail, None)
	
	def insertRouteWaypoint(self, navpoint):
		route = self.lookup(parsed_route_detail)
		assert route != None, 'Strip.insertRouteWaypoint: invalid route'
		lost_specs = route.insertWaypoint(navpoint)
		self.details[FPL.ROUTE] = route.enRouteStr() # bypass parse induced by writeDetail method
		return lost_specs
	
	def removeRouteWaypoint(self, navpoint):
		route = self.lookup(parsed_route_detail)
		assert route != None, 'Strip.removeRouteWaypoint: invalid route'
		lost_specs = route.removeWaypoint(navpoint)
		self.details[FPL.ROUTE] = route.enRouteStr() # bypass parse induced by writeDetail method
		return lost_specs







## DETAIL STRING CONVERSIONS

def detail2str(d, v):
	if d in [FPL.CALLSIGN, FPL.ACFT_TYPE, FPL.WTC, FPL.ICAO_DEP, FPL.ICAO_ARR, FPL.ICAO_ALT, \
			FPL.CRUISE_ALT, FPL.ROUTE, FPL.COMMENTS, FPL.FLIGHT_RULES, assigned_altitude_detail]: # str
		vstr = v
	elif d in [FPL.SOULS, assigned_SQ_detail]: # int
		vstr = str(v)
	elif d in [FPL.TAS, assigned_speed_detail]: # Speed
		vstr = str(int(v.kt))
	elif d == FPL.TIME_OF_DEP: # datetime
		vstr = '%d %d %d %d %d' % (v.year, v.month, v.day, v.hour, v.minute)
	elif d == FPL.EET: # timedelta
		vstr = str(int(v.total_seconds()))
	elif d == assigned_heading_detail: # Heading
		vstr = str(int(v.read()))
	else:
		raise ValueError('Unknown key for detail conversion: %s' % d)
	return str(d), vstr # CAUTION this assumes there is no str detail key that looks like an int


def str2detail(dstr, vstr):
	try:
		d = int(dstr) # CAUTION this assumes there is no str detail key that looks like an int
	except ValueError:
		d = dstr
	if d in [FPL.CALLSIGN, FPL.ACFT_TYPE, FPL.WTC, FPL.ICAO_DEP, FPL.ICAO_ARR, FPL.ICAO_ALT, \
			FPL.CRUISE_ALT, FPL.ROUTE, FPL.COMMENTS, FPL.FLIGHT_RULES, assigned_altitude_detail]: # str
		v = vstr
	elif d in [FPL.SOULS, assigned_SQ_detail]: # int
		v = int(vstr)
	elif d in [FPL.TAS, assigned_speed_detail]: # Speed
		v = Speed(int(vstr))
	elif d == FPL.TIME_OF_DEP: # datetime
		year, month, day, hour, minute = vstr.split()
		v = datetime(year=int(year), month=int(month), day=int(day),
						hour=int(hour), minute=int(minute), tzinfo=timezone.utc)
	elif d == FPL.EET: # timedelta
		v = timedelta(seconds=int(vstr))
	elif d == assigned_heading_detail: # Heading
		v = Heading(int(vstr), False)
	else:
		raise ValueError('Unknown key for detail conversion: %s' % dstr)
	return d, v



