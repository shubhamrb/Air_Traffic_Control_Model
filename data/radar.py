
from PyQt5.QtCore import pyqtSignal, QObject

from session.config import settings
from session.env import env

from data.util import pop_all
from data.coords import m2NM
from data.strip import soft_link_detail, assigned_SQ_detail, runway_box_detail, received_from_detail
from data.fpl import FPL
from data.utc import now
from data.acft import Aircraft
from data.conflict import Conflict, position_conflict_test, path_conflict_test

from gui.misc import signals, Ticker


# ---------- Constants ----------

XPDR_emergency_codes = [0o7500, 0o7600, 0o7700]

# -------------------------------


class Radar(QObject):
	blip = pyqtSignal()
	newContact = pyqtSignal(Aircraft)
	lostContact = pyqtSignal(Aircraft)
	emergencySquawk = pyqtSignal(Aircraft)
	runwayIncursion = pyqtSignal(int, Aircraft)
	pathConflict = pyqtSignal()
	nearMiss = pyqtSignal()
	
	def __init__(self, gui):
		QObject.__init__(self)
		self.ticker = Ticker(self.scan, parent=gui)
		self.last_sweep = now() # to be updated with current time at each blip
		self.aircraft_list = []          # Aircraft list
		self.blips_invisible = {}        # str -> int; number of blips for which ACFT callsign has been invisible
		self.soft_links = []             # (Strip, Aircraft) pairs
		self.known_EMG_squawkers = set() # str identifiers
		self.runway_occupation = {}      # int -> list of ACFT identifiers
		if env.airport_data != None:
			for i in range(env.airport_data.physicalRunwayCount()):
				self.runway_occupation[i] = []
	
	def startSweeping(self):
		self.ticker.start_stopOnZero(settings.radar_sweep_interval)
	
	def stopSweeping(self):
		self.ticker.stop()
	
	def scan(self):
		visible_aircraft = { a.identifier: a for a in settings.session_manager.getAircraft() if a.isRadarVisible() }
		
		## UPDATE AIRCRAFT LIST
		lost_contacts = []
		for got_acft in self.aircraft_list:
			try:
				ignore = visible_aircraft.pop(got_acft.identifier)
				got_acft.saveRadarSnapshot()
				self.blips_invisible[got_acft.identifier] = 0
			except KeyError:
				count = self.blips_invisible[got_acft.identifier]
				if count < settings.invisible_blips_before_contact_lost:
					self.blips_invisible[got_acft.identifier] = count + 1
				else:
					lost_contacts.append(got_acft.identifier)
		# Remove lost aircraft
		for acft in pop_all(self.aircraft_list, lambda acft: acft.identifier in lost_contacts):
			strip = env.linkedStrip(acft)
			del self.blips_invisible[acft.identifier]
			self.known_EMG_squawkers.discard(acft.identifier)
			self.lostContact.emit(acft)
			if strip != None:
				signals.controlledContactLost.emit(strip, acft.coords())
		# Add newly visible aircraft
		for new_acft in visible_aircraft.values():
			new_acft.saveRadarSnapshot()
			self.aircraft_list.append(new_acft)
			self.blips_invisible[new_acft.identifier] = 0
			self.newContact.emit(new_acft)
		
		## CHECK FOR NEW EMERGENCIY SQUAWKS
		for acft in self.aircraft_list:
			if acft.xpdrCode() in XPDR_emergency_codes:
				if acft.identifier not in self.known_EMG_squawkers:
					self.known_EMG_squawkers.add(acft.identifier)
					self.emergencySquawk.emit(acft)
			else:
				self.known_EMG_squawkers.discard(acft.identifier)
		
		## CHECK FOR NEW/LOST RADAR IDENTIFICATIONS
		if settings.traffic_identification_assistant:
			found_S_links = []
			found_A_links = []
			for strip in env.strips.listStrips(lambda s: s.linkedAircraft() == None):
				mode_S_found = False
				# Try mode S identification
				if strip.lookup(FPL.CALLSIGN) != None:
					scs = strip.lookup(FPL.CALLSIGN).upper()
					if env.strips.count(lambda s: s.lookup(FPL.CALLSIGN) != None and s.lookup(FPL.CALLSIGN).upper() == scs) == 1:
						candidates = [acft for acft in self.aircraft_list if acft.xpdrCallsign() != None and acft.xpdrCallsign().upper() == scs]
						if len(candidates) == 1:
							found_S_links.append((strip, candidates[0]))
							mode_S_found = True
				# Try mode A identification
				if not mode_S_found:
					ssq = strip.lookup(assigned_SQ_detail)
					if ssq != None and env.strips.count(lambda s: \
							s.lookup(assigned_SQ_detail) == ssq and s.linkedAircraft() == None) == 1: # only one non-linked strip with this SQ
						candidates = [acft for acft in self.aircraft_list if not any(a is acft for s, a in found_S_links) \
							and acft.xpdrCode() == ssq and env.linkedStrip(acft) == None]
						if len(candidates) == 1: # only one aircraft matching
							found_A_links.append((strip, candidates[0]))
			for s, a in pop_all(self.soft_links, lambda sl: not any(sl[0] is s and sl[1] is a for s, a in found_S_links + found_A_links)):
				s.writeDetail(soft_link_detail, None)
			for s, a, m in [(s, a, True) for s, a in found_S_links] + [(s, a, False) for s, a in found_A_links]:
				if not any(sl[0] is s and sl[1] is a for sl in self.soft_links): # new found soft link
					if strip.lookup(received_from_detail) != None and settings.strip_autolink_on_ident and (m or settings.strip_autolink_include_modeC):
						s.linkAircraft(a)
					else: # strip not automatically linked; notify of a new identification
						self.soft_links.append((s, a))
						s.writeDetail(soft_link_detail, a)
						signals.aircraftIdentification.emit(s, a, m)
		
		## UPDATE POSITION/ROUTE WARNINGS
		conflicts = { acft.identifier: Conflict.NO_CONFLICT for acft in self.aircraft_list }
		traffic_for_route_checks = []
		for strip in env.strips.listStrips(): # check for position conflicts and build list of traffic to check for routes later
			acft = strip.linkedAircraft()
			if acft != None and acft.identifier in conflicts: # controlled traffic with radar contact
				for other in self.aircraft_list:
					if other is not acft and position_conflict_test(acft, other) == Conflict.NEAR_MISS: # positive separation loss detected
						conflicts[acft.identifier] = conflicts[other.identifier] = Conflict.NEAR_MISS
				if not bypass_route_conflict_check(strip):
					traffic_for_route_checks.append(acft)
		if settings.route_conflict_warnings: # check for route conflicts
			while traffic_for_route_checks != []: # progressively emptying the list
				acft = traffic_for_route_checks.pop()
				for other in traffic_for_route_checks:
					c = path_conflict_test(acft, other)
					conflicts[acft.identifier] = max(conflicts[acft.identifier], c)
					conflicts[other.identifier] = max(conflicts[other.identifier], c)
		# now update aircraft conflicts and emit signals if any are new
		new_near_miss = new_path_conflict = False
		for contact in self.aircraft_list:
			new_conflict = conflicts[contact.identifier]
			if new_conflict > contact.conflict:
				new_near_miss |= new_conflict == Conflict.NEAR_MISS
				new_path_conflict |= new_conflict in [Conflict.DEPENDS_ON_ALT, Conflict.PATH_CONFLICT]
			contact.conflict = new_conflict
		if new_path_conflict:
			self.pathConflict.emit()
		if new_near_miss:
			self.nearMiss.emit()
		
		## UPDATE RUNWAY OCCUPATION
		for phrwy in self.runway_occupation:
			new_occ = []
			if settings.monitor_runway_occupation:
				rwy1, rwy2 = env.airport_data.physicalRunway(phrwy)
				width_metres = env.airport_data.physicalRunwayData(phrwy)[0]
				thr1 = rwy1.threshold().toRadarCoords()
				thr2 = rwy2.threshold().toRadarCoords()
				w = m2NM * width_metres
				for acft in self.aircraft_list:
					if acft.considerOnGround():
						if acft.coords().toRadarCoords().isBetween(thr1, thr2, w / 2): # ACFT is on RWY
							new_occ.append(acft)
							if not any(a is acft for a in self.runway_occupation[phrwy]): # just entered the RWY: check if alarm must sound
								try:
									boxed_link = env.strips.findStrip(lambda strip: strip.lookup(runway_box_detail) == phrwy).linkedAircraft()
								except StopIteration: # no strip boxed on this runway
									if rwy1.inUse() or rwy2.inUse(): # entering a non-reserved but active RWY
										self.runwayIncursion.emit(phrwy, acft)
								else: # RWY is reserved
									if boxed_link == None and env.linkedStrip(acft) == None or boxed_link is acft:
										# entering ACFT is the one cleared to enter, or can be
										if self.runway_occupation[phrwy] != []: # some ACFT was/were already on RWY
											call_guilty = acft if boxed_link == None else self.runway_occupation[phrwy][0]
											self.runwayIncursion.emit(phrwy, call_guilty)
									else: # entering ACFT is known to be different from the one cleared to enter
										self.runwayIncursion.emit(phrwy, acft)
			self.runway_occupation[phrwy] = new_occ
		
		# Finished aircraft stuff
		self.last_sweep = now()
		self.blip.emit()
	
	def runwayOccupation(self, phrwy):
		return self.runway_occupation[phrwy]
	
	def missedOnLastScan(self, acft_id):
		'''
		True if ACFT is known (i.e. not already lost) but was not picked up on last radar scan.
		'''
		try:
			return self.blips_invisible[acft_id] > 0
		except KeyError:
			return False
	
	def contacts(self):
		'''
		Returns a list of connected aircraft contacts
		'''
		return self.aircraft_list[:]
	
	def resetContacts(self):
		self.aircraft_list.clear()
		self.blips_invisible.clear()
		self.soft_links.clear()
		self.known_EMG_squawkers.clear()
		for phrwy in self.runway_occupation:
			self.runway_occupation[phrwy].clear()
	
	def silentlyForgetContact(self, killed):
		for popped in pop_all(self.aircraft_list, lambda acft: acft is killed): # there should only be one
			del self.blips_invisible[killed.identifier]
			self.known_EMG_squawkers.discard(killed.identifier)





def bypass_route_conflict_check(strip):
	rules = strip.lookup(FPL.FLIGHT_RULES, fpl=True)
	return settings.route_conflict_traffic == 0 and rules == 'VFR' or settings.route_conflict_traffic == 1 and rules != 'IFR'

