
from session.config import settings
from session.env import env

from data.utc import now
from data.params import Speed, StdPressureAlt
from data.conflict import Conflict


# ---------- Constants ----------

snapshot_history_size = 120 # number of radar snapshots
snapshot_diff_time = 6 # seconds (how long to look back in history for snapshot diffs)
min_taxiing_speed = Speed(5)
max_ground_height = 100 # ft

# -------------------------------



class Xpdr:
	all_keys = CODE, IDENT, ALT, CALLSIGN, ACFT, GND, IAS = range(7)



class RadarSnapshot:
	def __init__(self, time_stamp, coords, geom_alt):
		# Obligatory constructor data
		self.time_stamp = time_stamp
		self.coords = coords
		self.geometric_alt = geom_alt
		# XPDR data
		self.xpdrData = {}
		# Inferred values
		self.heading = None
		self.groundSpeed = None
		self.verticalSpeed = None





class Aircraft:
	'''
	This class represents a live aircraft, whether visible or invisible.
	'''
	
	def __init__(self, identifier, acft_type, init_position, init_geom_alt):
		self.identifier = identifier # assumed unique
		self.aircraft_type = acft_type
		# "REAL TIME" VALUES
		self.live_update_time = now()
		self.live_position = init_position, init_geom_alt # EarthCoords, geom AMSL
		self.live_XPDR_data = {} # sqkey -> value mappings available from live update
		# UPDATED DATA
		init_snapshot = RadarSnapshot(self.live_update_time, init_position, init_geom_alt)
		self.radar_snapshots = [init_snapshot] # snapshot history; list must not be empty
		self.conflict = Conflict.NO_CONFLICT
		# USER OPTIONS
		self.individual_cheat = False
		self.ignored = False
		# FLAGS
		self.spawned = True
		self.frozen = False
	
	def __str__(self):
		return self.identifier
	
	def setIndividualCheat(self, b):
		self.individual_cheat = b
		self.saveRadarSnapshot()
	
	
	## LIVE DATA QUERY AND UPDATE
	
	def liveCoords(self):
		return self.live_position[0]
	
	def liveGeometricAlt(self):
		return self.live_position[1]
	
	def lastLiveUpdateTime(self):
		return self.live_update_time
	
	def isRadarVisible(self):
		'''
		a radar can draw a spot (possibly helped by a cheat)
		'''
		if self.individual_cheat:
			return True
		visible = settings.radar_cheat \
						or settings.primary_radar_active \
						or settings.SSR_mode_capability != '0' and self.live_XPDR_data != {} # radar contact
		visible &= settings.radar_signal_floor_level == 0 \
						or settings.radar_cheat \
						or self.liveGeometricAlt() >= settings.radar_signal_floor_level # vert. range
		visible &= env.pointInRadarRange(self.liveCoords()) # horiz. range
		return visible
	
	def updateLiveStatus(self, pos, geom_alt, xpdr_data):
		self.live_update_time = now()
		self.live_position = pos, geom_alt
		self.live_XPDR_data = xpdr_data
	
	
	## RADAR SNAPSHOTS
	
	def lastSnapshot(self):
		return self.radar_snapshots[-1]
	
	def positionHistory(self, hist):
		'''
		returns the history of snapshot coordinates for the given delay since last live update, in chronological order.
		'''
		try:
			i_start = next(i for i, snap in enumerate(self.radar_snapshots) if self.live_update_time - snap.time_stamp <= hist)
			return [snap.coords for snap in self.radar_snapshots[i_start:]]
		except StopIteration: # if no live update in the time frame requested (can happen if app freezes for a while)
			return []
	
	def moveHistoryTimesForward(self, delay):
		self.live_update_time += delay
		for snap in self.radar_snapshots:
			snap.time_stamp += delay
	
	def saveRadarSnapshot(self):
		prev = self.lastSnapshot() # always exists
		if prev.time_stamp == self.live_update_time:
			return # No point saving values again: they were not updated since last snapshot
		
		# otherwise create a new snapshot
		snapshot = RadarSnapshot(self.live_update_time, self.liveCoords(), self.liveGeometricAlt())
		snapshot.xpdrData = self.live_XPDR_data.copy()
		if settings.radar_cheat or self.individual_cheat:
			# We try to compensate, but cannot always win so None values are possible.
			# Plus: CODE, IDENT and GND have no useful compensation.
			if Xpdr.ALT not in snapshot.xpdrData:
				stdpa = StdPressureAlt.fromAMSL(snapshot.geometric_alt, env.QNH())
				snapshot.xpdrData[Xpdr.ALT] = StdPressureAlt(stdpa.ft1013())
			if Xpdr.CALLSIGN not in snapshot.xpdrData:
				snapshot.xpdrData[Xpdr.CALLSIGN] = self.identifier
			if Xpdr.ACFT not in snapshot.xpdrData:
				snapshot.xpdrData[Xpdr.ACFT] = self.aircraft_type
		else: # contact is not cheated
			if settings.SSR_mode_capability == '0': # no SSR so no XPDR data can be snapshot
				snapshot.xpdrData.clear()
			else: # SSR on; check against A/C/S capability
				if settings.SSR_mode_capability == 'A': # radar does not have the capability to pick up altitude
					if Xpdr.ALT in snapshot.xpdrData:
						del snapshot.xpdrData[Xpdr.ALT]
				if settings.SSR_mode_capability != 'S': # radar does not have mode S interrogation capability
					for k in (Xpdr.CALLSIGN, Xpdr.ACFT, Xpdr.IAS, Xpdr.GND):
						if k in snapshot.xpdrData:
							del snapshot.xpdrData[k]
		
		# Inferred values
		if self.frozen: # copy from previous snapshot
			snapshot.heading = prev.heading
			snapshot.groundSpeed = prev.groundSpeed
			snapshot.verticalSpeed = prev.verticalSpeed
		else: # compute values from change between snapshots
			# Search history for best snapshot to use for diff
			diff_seconds = (snapshot.time_stamp - prev.time_stamp).total_seconds()
			i = 1 # index of currently selected prev
			while i < len(self.radar_snapshots) and diff_seconds < snapshot_diff_time:
				i += 1
				prev = self.radar_snapshots[-i]
				diff_seconds = (snapshot.time_stamp - prev.time_stamp).total_seconds()
			# Fill snapshot diffs
			if prev.coords != None and snapshot.coords != None:
				# ground speed
				snapshot.groundSpeed = Speed(prev.coords.distanceTo(snapshot.coords) * 3600 / diff_seconds)
				# heading
				if snapshot.groundSpeed != None and snapshot.groundSpeed.diff(min_taxiing_speed) > 0: # acft moving across the ground
					try: snapshot.heading = snapshot.coords.headingFrom(prev.coords)
					except ValueError: snapshot.heading = prev.heading # stopped: keep prev. hdg
				else:
					snapshot.heading = prev.heading
			# vertical speed
			prev_alt = prev.xpdrData.get(Xpdr.ALT, None)
			this_alt = snapshot.xpdrData.get(Xpdr.ALT, None)
			if prev_alt != None and this_alt != None:
				snapshot.verticalSpeed = (this_alt.diff(prev_alt)) * 60 / diff_seconds
		
		# Append snapshot to history
		self.radar_snapshots.append(snapshot)
		if len(self.radar_snapshots) > snapshot_history_size:
			del self.radar_snapshots[0]
	
	
	## DATA QUERY (READING FROM LATEST SNAPSHOT)
	
	def coords(self):
		return self.lastSnapshot().coords
	
	## Squawked values
	
	def xpdrOn(self):
		return self.lastSnapshot().xpdrData != {}
	
	def xpdrCode(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.CODE, None)
	
	def xpdrIdent(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.IDENT, None)
	
	def xpdrAlt(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.ALT, None)
	
	def xpdrCallsign(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.CALLSIGN, None)
	
	def xpdrAcftType(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.ACFT, None)
	
	def xpdrIAS(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.IAS, None)
	
	def xpdrGND(self):
		return self.lastSnapshot().xpdrData.get(Xpdr.GND, None)
	
	## Inferred values
	
	def heading(self):
		return self.lastSnapshot().heading
	
	def groundSpeed(self):
		return self.lastSnapshot().groundSpeed
	
	def verticalSpeed(self):
		return self.lastSnapshot().verticalSpeed
	
	def considerOnGround(self):
		return self.xpdrGND() \
				or self.xpdrAlt() != None and self.lastSnapshot().geometric_alt - env.elevation(self.coords()) <= max_ground_height
	
	def IAS(self):
		'''
		Get real IAS if squawked, or estimate. None result is possible if missing alt or ground speed.
		When estimating: TAS = ground speed (no wind correction because wind is not known here).
		'''
		squawked = self.xpdrIAS()
		if squawked != None:
			return squawked
		# else: estimate...
		gs = self.lastSnapshot().groundSpeed
		if gs != None:
			alt = self.xpdrAlt()
			if alt != None:
				return gs.tas2ias(alt)
		return None


