from session.config import settings

from data.util import pop_all, some, rounded
from data.coords import EarthCoords
from data.strip import assigned_SQ_detail
from data.fpl import FPL
from data.weather import Weather
from data.params import Heading, StdPressureAlt
from data.utc import timestr


# ---------- Constants ----------

default_tower_height = 300 # ft

# -------------------------------

class Environment:
	'''
	Things that are updated during the running session
	'''
	def __init__(self):
		# To set manually before a main window session (location set-up)
		self.airport_data = None        # remains None in CTR mode
		self.elevation_map = None       # optionally set
		self.frequencies = []           # (frq, descr, type) list
		self.navpoints = None           # Navpoints in range
		# Qt objects emitting signals to disconnect before being replaced between sessions:
		self.radar = None            # set once and persistent
		self.rdf = None              # set once and persistent
		self.cpdlc = None            # CPDLC message history model
		self.strips = None           # Full strip list model
		self.discarded_strips = None # Discarded strip model
		self.FPLs = None             # FPL model
		self.ATCs = None             # ATCs available in handover range
	
	def resetEnv(self):
		self.airport_data = None
		self.elevation_map = None
		self.frequencies.clear()
		self.navpoints = None
		for qtobj in self.radar, self.rdf, self.cpdlc, self.strips, self.discarded_strips, self.FPLs, self.ATCs:
			qtobj.disconnect()
		self.radar = None
		self.rdf = None
		self.cpdlc = None
		self.strips = None
		self.discarded_strips = None
		self.FPLs = None
		self.ATCs = None
	
	def locationName(self):
		return 'Control centre' if self.airport_data == None else self.airport_data.navpoint.long_name
	
	def elevation(self, coords):
		if self.elevation_map != None:
			try:
				return self.elevation_map.elev(coords.toRadarCoords())
			except ValueError:
				pass
		return 0 if self.airport_data == None else self.airport_data.field_elevation
	
	def radarPos(self):
		return EarthCoords.getRadarPos()
	
	def viewpoint(self):
		'''
		returns EarthCoords, float ft AMSL pair specifying current viewpoint's position
		'''
		try:
			pos, h, name = self.airport_data.viewpoints[settings.selected_viewpoint]
		except IndexError:
			pos = self.airport_data.navpoint.coordinates
			h = default_tower_height
		return pos, self.elevation(pos) + h + settings.tower_height_cheat_offset
	
	def pointInRadarRange(self, coords):
		return self.radarPos().distanceTo(coords) <= settings.radar_range
	
	def pointOnMap(self, coords):
		return self.radarPos().distanceTo(coords) <= settings.map_range
	
	def linkedStrip(self, item): # item must be FPL or Aircraft
		try:
			if isinstance(item, FPL):
				return self.strips.findStrip(lambda s: s.linkedFPL() is item)
			else: # Aircraft
				return self.strips.findStrip(lambda s: s.linkedAircraft() is item)
		except StopIteration:
			return None
				
		except StopIteration:
			return None
	
	def knownCallsigns(self):
		callsigns = set()
		for acft in self.radar.contacts():
			callsigns.add(acft.xpdrCallsign())
		for strip in self.strips.listStrips():
			callsigns.add(strip.callsign(fpl=True))
		for atc in self.ATCs.knownATCs():
			callsigns.add(atc)
		callsigns.discard(None)
		return callsigns
	
	def primaryWeather(self):
		return settings.session_manager.getWeather(settings.primary_METAR_station)
	
	def nextSquawkCodeAssignment(self, assignment_range):
		most_free = None
		mem_count = float('+inf')
		for sq in range(assignment_range.lo, assignment_range.hi + 1):
			count = len(self.strips.listStrips(lambda s: s.lookup(assigned_SQ_detail) == sq))
			if count == 0: # Code is not assigned
				return sq
			elif count < mem_count:
				most_free = sq
				mem_count = count
		return most_free
	
	def readDeclination(self):
		if Heading.declination != None:
			txt = '%.1f°' % abs(Heading.declination)
			if Heading.declination != 0:
				txt += 'EW'[Heading.declination < 0]
			return txt
	
	def transitionAltitude(self):
		if self.airport_data != None and self.airport_data.transition_altitude != None:
			return self.airport_data.transition_altitude
		else:
			return settings.transition_altitude
	
	def transitionLevel(self):
		'''
		Returns the lowest FL above the TA.
		This is NOT the lowest assignable, which takes more vertical separation
		'''
		return StdPressureAlt.fromAMSL(self.transitionAltitude(), self.QNH()).FL() + 1
	
	def QNH(self, noneSafe=True):
		w = self.primaryWeather()
		qnh = None if w == None else w.QNH()
		return some(qnh, 1013.25) if noneSafe else qnh
	
	def QFE(self, qnh):
		'''
		in AD mode, returns the ground level pressure (QFE), given MSL pressure
		'''
		return None if self.airport_data == None else qnh - self.airport_data.field_elevation / 28
	
	def groundStdPressureAlt(self, coords):
		return StdPressureAlt.fromAMSL(self.elevation(coords), self.QNH())
	
	def stdPressureAlt(self, reading):
		return StdPressureAlt.fromReading(reading, self.QNH())
	
	def readStdAlt(self, alt, step=1, unit=True):
		'''
		returns a string reading the altitude properly, i.e. a QNH-aware reading in feet AMSL under TA, and a flight level above TA.
		altitude readings are rounded to closest "step hundred"; FL readings are rounded with given step
		(use step=None for no approximation even in feet)
		"ft" is appended to string if 'unit' parameter is set
		'''
		amsl = alt.ftAMSL(self.QNH())
		if amsl < self.transitionAltitude() + settings.altitude_tolerance:
			return '%d%s' % ((amsl if step == None else rounded(amsl, 100 * step)), (' ft' if unit else ''))
		else:
			fl = alt.FL()
			return 'FL%03d' % (fl if step == None else rounded(fl, step))
	
	def RWD(self, hdg):
		'''
		relative wind direction for given heading
		'''
		w = self.primaryWeather()
		if w != None:
			wind = w.mainWind()
			if wind != None and wind[0] != None:
				return wind[0].opposite().diff(hdg)
		return None
	
	def suggestedATIS(self, letter, custom_appendix):
		if self.airport_data == None:
			return ''
		atis = 'This is %s information %s recorded at %s UTC' \
			% ((settings.location_radio_name if settings.location_radio_name else self.locationName()), letter, timestr())
		if any(rwy.use_for_departures or rwy.use_for_arrivals for rwy in env.airport_data.allRunways()):
			atis += '\nRunway(s) in use: %s' % self.readRunwaysInUse()
		w = self.primaryWeather()
		if w == None:
			atis += '\nNo weather available'
		else:
			atis += '\nWind %s' % w.readWind()
			atis += '\nVisibility %s' % w.readVisibility()
			temperatures = w.temperatures()
			if temperatures != None:
				atis += '\nTemp. %d °C, dew point %d °C' % temperatures
			qnh = w.QNH()
			atis += '\nQNH N/A' if qnh == None else '\nQNH %d, QFE %d' % (qnh, self.QFE(qnh))
		if custom_appendix:
			atis += '\n\n' + custom_appendix
		atis += '\n\nAdvise %s on initial contact that you have received information %s' \
			% ((settings.location_radio_name if settings.location_radio_name else 'ATC'), letter)
		return atis
	
	def readRunwaysInUse(self):
		if self.airport_data == None:
			return 'N/A'
		dep = [rwy.name for rwy in self.airport_data.allRunways() if rwy.use_for_departures]
		arr = [rwy.name for rwy in self.airport_data.allRunways() if rwy.use_for_arrivals]
		if dep + arr == []:
			return 'N/A'
		both = pop_all(dep, lambda rwy: rwy in arr)
		pop_all(arr, lambda rwy: rwy in both)
		res = '' if both == [] else '/'.join(both) + ' for dep+arr'
		if dep != []:
			if res != '':
				res += ', '
			res += '%s for departures' % '/'.join(dep)
		if arr != []:
			if res != '':
				res += ', '
			res += '%s for arrivals' % '/'.join(arr)
		return res


env = Environment()

