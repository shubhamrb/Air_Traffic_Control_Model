
from datetime import timedelta

from session.config import settings
from session.env import env

from data.util import ordered_pair, intervals_intersect, flatten
from data.coords import breakUpLine, m2NM
from data.params import StdPressureAlt, distance_flown, Speed
from data.strip import assigned_heading_detail, parsed_route_detail
from data.db import wake_turb_cat


# ---------- Constants ----------

route_division_ttf = timedelta(minutes=1)
min_path_hop_when_not_dividing = .5 # NM

bulk_radii_metres = {'L': 7, 'M': 25, 'H': 40, 'J': 45}
default_bulk_radius = 25 # m

# -------------------------------


class Conflict:
	NO_CONFLICT, DEPENDS_ON_ALT, PATH_CONFLICT, NEAR_MISS = range(4) # CAUTION: Order is used for comparison


class NoPath(Exception):
	pass



def shapes_intersect(sh1, sh2):
	'''
	a shape is a list of connected lines
	'''
	for r1 in sh1:
		r1a = r1[0].toRadarCoords()
		r1b = r1[1].toRadarCoords()
		for r2 in sh2:
			r2a = r2[0].toRadarCoords()
			r2b = r2[1].toRadarCoords()
			if intervals_intersect(ordered_pair(r1a.x(), r1b.x()), ordered_pair(r2a.x(), r2b.x())) \
					and intervals_intersect(ordered_pair(r1a.y(), r1b.y()), ordered_pair(r2a.y(), r2b.y())):
				return True
	return False






# auxiliary function, returns 4-uple:
# segments of broken down route section, end point, distance flown, waypoints left
def horizontal_route(pos, waypoints, distance_to_fly):
	if waypoints == [] or distance_to_fly <= 0:
		return [], pos, 0, waypoints
	else:
		wp = waypoints[0]
		wp_dist = pos.distanceTo(wp)
		if wp_dist <= distance_to_fly: # waypoint encountered
			rest_of_route, end_point, rest_of_dist, waypoints_left = horizontal_route(wp, waypoints[1:], distance_to_fly - wp_dist)
			return breakUpLine(pos, wp) + rest_of_route, end_point, wp_dist + rest_of_dist, waypoints_left
		else: # path stops before any waypoints
			end_point = pos.moved(pos.headingTo(wp), distance_to_fly)
			return breakUpLine(pos, end_point), end_point, distance_to_fly, waypoints




def horizontal_route_divisions(pos, waypoints, div_dist, limit=None):
	divisions = []
	acc_dist = 0
	while waypoints != [] and (env.pointInRadarRange(pos) or env.pointOnMap(pos) if limit == None else acc_dist < limit):
		div_path, end_point, distance_flown, waypoints = horizontal_route(pos, waypoints, div_dist)
		divisions.append(div_path)
		pos = end_point
		acc_dist += distance_flown
	return divisions




def horizontal_path(acft, hdg=True, rte=True, ttf=None, div=False):
	'''
	Returns the anticipated ACFT path, considering headings (if "hdg") and/or routes (if "rte"), until
	route destination is reached, "ttf" is given and flown, or path goes out of both map and radar ranges.
	If "div" is True, the returned list is divided into sections flown in one "route division time".
	NB: Heading assignments override routes if both are considered.
	'''
	speed = acft.groundSpeed()
	if speed != None:
		strip = env.linkedStrip(acft)
		if strip != None:
			pos = acft.coords()
			waypoints = None
			if hdg:
				assHdg = strip.lookup(assigned_heading_detail)
				if assHdg != None:
					wp_dist = 2 * max(settings.map_range, settings.radar_range) if ttf == None else distance_flown(ttf, speed)
					waypoints = [pos.moved(assHdg, wp_dist)]
			if waypoints == None and rte:
				route = strip.lookup(parsed_route_detail)
				if route != None:
					waypoints = [route.waypoint(i).coordinates for i in range(route.currentLegIndex(pos), route.legCount())]
			if waypoints != None:
				dist_limit = None if ttf == None else distance_flown(ttf, speed)
				div_dist = distance_flown(route_division_ttf, speed)
				if div_dist < min_path_hop_when_not_dividing and dist_limit == None:
					if div:
						raise ValueError('ACFT speed too low to calculate path and count on divisions with no TTF limit')
					else: # set to fall-back value, shortcutting ACFT speed but resulting div's are flattened anyway (not wanted)
						div_dist = min_path_hop_when_not_dividing
				divisions = horizontal_route_divisions(pos, waypoints, div_dist, limit=dist_limit)
				return divisions if div else flatten(divisions)
	raise NoPath()











def vertical_assignment(acft):
	strip = env.linkedStrip(acft)
	if strip == None:
		return None
	else:
		alt = strip.assignedPressureAlt(env.QNH())
		return None if alt == None else alt.ft1013()



def position_conflict_test(acft1, acft2):
	alt1 = acft1.xpdrAlt()
	alt2 = acft2.xpdrAlt()
	if alt1 != None and alt1.FL() < settings.conflict_warning_floor_FL \
			or alt2 != None and alt2.FL() < settings.conflict_warning_floor_FL \
			or acft1.coords().distanceTo(acft2.coords()) >= settings.horizontal_separation:
		return Conflict.NO_CONFLICT
	elif alt1 == None or alt2 == None:
		return Conflict.DEPENDS_ON_ALT
	elif abs(alt1.diff(alt2)) < settings.vertical_separation:
		return Conflict.NEAR_MISS
	else:
		return Conflict.NO_CONFLICT



def path_conflict_test(acft1, acft2):
	alt1 = acft1.xpdrAlt()
	alt2 = acft2.xpdrAlt()
	if alt1 != None and alt1.FL() < settings.conflict_warning_floor_FL \
			or alt2 != None and alt2.FL() < settings.conflict_warning_floor_FL:
		return Conflict.NO_CONFLICT
	try:
		divs1 = horizontal_path(acft1, hdg=True, rte=True, ttf=settings.route_conflict_anticipation, div=True)
		divs2 = horizontal_path(acft2, hdg=True, rte=True, ttf=settings.route_conflict_anticipation, div=True)
	except NoPath:
		return Conflict.NO_CONFLICT
	for i, div1 in enumerate(divs1):
		for div2 in divs2[max(0, i-1) : i+2]:
			if shapes_intersect(div1, div2): # heading or route assigned to both, and in conflict; check for altitudes
				ass1 = vertical_assignment(acft1)
				ass2 = vertical_assignment(acft2)
				if ass1 == None or ass2 == None:
					return Conflict.DEPENDS_ON_ALT
				else: # both ACFT have an assigned alt.
					vi1 = (ass1, ass1) if alt1 == None else ordered_pair(alt1.ft1013(), ass1)
					vi2 = (ass2, ass2) if alt2 == None else ordered_pair(alt2.ft1013(), ass2)
					return Conflict.PATH_CONFLICT if intervals_intersect(vi1, vi2) else Conflict.NO_CONFLICT
	return Conflict.NO_CONFLICT




def acft_bulk_radius(acft_type):
	return bulk_radii_metres.get(wake_turb_cat(acft_type), default_bulk_radius) * m2NM

def ground_separated(acft, other_pos, other_type):
	return acft.coords().distanceTo(other_pos) >= acft_bulk_radius(acft.aircraft_type) + acft_bulk_radius(other_type)

