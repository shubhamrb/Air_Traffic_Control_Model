from PyQt5.QtCore import QThread
from xml.etree import ElementTree
from time import sleep
from socket import timeout

from urllib.parse import urlencode
from urllib.error import URLError

from session.manager import HandoverBlocked
from session.config import settings, open_URL
from session.env import env

from data.util import some
from data.coords import EarthCoords
from data.params import StdPressureAlt, Speed
from data.comms import CommFrequency
from data.fpl import FPL
from data.strip import Strip, received_from_detail, assigned_altitude_detail, assigned_SQ_detail

from models.ATCs import ATC
from gui.misc import Ticker, signals


# ---------- Constants ----------

SX_update_interval = 3 * 1000 # milliseconds
ATCpie_hidden_string = '__ATC-pie__' # to recognise ATC-pie sender in <pilot> elements

ORSX_account_name = 'ATC-pie'
ORSX_account_password = ''

# -------------------------------







def server_query(cmd, dict_data):
	qdict = {
		'user': ORSX_account_name,
		'password': ORSX_account_password,
		'atc': settings.session_manager.myCallsign()
	}
	if env.airport_data != None:
		qdict['airport'] = settings.location_code
	qdict.update(dict_data)
	try:
		#print('\nPOST %s DATA: %s' % (cmd, post_data))
		response = open_URL('%s/%s' % (settings.ORSX_server_name, cmd), postData=bytes(urlencode(qdict), encoding='utf8'))
		#print('RESPONSE: %s\n' % response)
		return response
	except (URLError, timeout) as error:
		print('URL error or request timed out: %s' % error)



def send_update_msg(fgms_id, strip, owner, handover):
	xml = ElementTree.Element('flightplanlist')
	xml.set('version', '1.0')
	xml.append(make_WW_XML(fgms_id, strip, owner, handover))
	qdict = {'flightplans': ElementTree.tostring(xml)}
	return server_query('updateFlightplans', qdict) != None # returns True if OK



def send_update(fgms_id, strip, handover=None): # if handover None: acknowledge strip
	# 1st message is identical between handover and acknowledgement
	if send_update_msg(fgms_id, strip, settings.session_manager.myCallsign(), ''): # 1st message OK
		sleep(2)
		if handover == None:
			if not send_update_msg(fgms_id, strip, '', ''): # 2nd acknowledgement message fails
				print('ERROR: Received strip probably seen as yours by OpenRadar users.')
		else:
			if not send_update_msg(fgms_id, strip, settings.session_manager.myCallsign(), handover): # 2nd handver message fails
				print('ERROR sending handover. Strip probably seen as yours by OpenRadar users.')
				signals.handoverFailure.emit(strip, 'Could not send handover request.')
	else: # 1st message failed
		if handover == None:
			print('ERROR: Received strip probably seen as pending handover by OpenRadar users.')
		else:
			print('ERROR claiming ownership. Strip probably owned by an OpenRadar user.')
			signals.handoverFailure.emit(strip, 'Could not claim ownership of contact for handover.')














## MAIN CLASS


class WwStripExchanger:
	def __init__(self, gui):
		self.updater = SxUpdater(gui)
		self.update_ticker = Ticker(self.updater.start, parent=gui)
		self.gui = gui
		self.running = False
	
	def start(self):
		self.update_ticker.start(SX_update_interval)
		self.running = True
	
	def stopAndWait(self):
		if self.isRunning(): # CHECK: do we need to wait for any running SXsender threads as well?
			self.update_ticker.stop()
			self.updater.wait()
			self.running = False
		self.updater.ATCs_on_last_run.clear()
		self.updater.current_contact_claims.clear()
	
	def isRunning(self):
		return self.running
	
	def connectedATCs(self):
		return self.updater.ATCs_on_last_run[:]
	
	def isConnected(self, atc_callsign):
		return any(atc.callsign == atc_callsign for atc in self.updater.ATCs_on_last_run)
	
	def claimingContact(self, callsign):
		return self.updater.current_contact_claims.get(callsign, None)
	
	def handOver(self, strip, atc_id):
		'''
		returns cleanly if transfer is properly initiated (contact linked),
		otherwise: HandoverBlocked (handover aborted)
		'''
		acft = strip.linkedAircraft()
		if acft == None:
			raise HandoverBlocked('Unlinked strips cannot be sent through the OpenRadar system.')
		else:
			SXsender(self.gui, strip, acft.identifier, handover=atc_id).start()


# ------------------------------------------------------------------------------



class SXsender(QThread):
	def __init__(self, gui, strip, fgms_callsign, handover):
		QThread.__init__(self, parent=gui)
		self.fgms_id = fgms_callsign
		self.strip = strip
		self.handover = handover
	
	def run(self):
		send_update(self.fgms_id, self.strip, handover=self.handover)




class SxUpdater(QThread):
	def __init__(self, gui):
		QThread.__init__(self, parent=gui)
		self.ATCs_on_last_run = [] # list of ATC objects
		self.current_contact_claims = {} # claimed ACFT callsign -> claiming ATC callsign
	
	def run(self):
		## PREPARING QUERY
		pos = env.radarPos()
		qdict = {
			'username': settings.MP_social_name,
      'lon': pos.lon,
      'lat': pos.lat,
      'range': some(settings.ORSX_handover_range, settings.radar_range),
      'xmlVersion': '1.0',
      'contacts': ','.join(acft.identifier for acft in env.radar.contacts()) # should this be all FGMS connections?
		}
		if settings.publicised_frequency != None:
			qdict['frequency'] = str(settings.publicised_frequency)
		server_response = server_query('getFlightplans', qdict)
		## USING RESPONSE
		if server_response != None:
			try:
				ww_root = ElementTree.fromstring(server_response)
			except ElementTree.ParseError as parse_error:
				print('Parse error in SX server data: %s' % parse_error)
				return
			new_ATCs = []
			
			# ATCs first
			for ww_atc in ww_root.find('atcsInRange').iter('atc'): # NOTE the server sends the full list each time
				atc = ATC(ww_atc.find('callsign').text)
				atc.social_name = ww_atc.find('username').text
				atc.position = EarthCoords(float(ww_atc.find('lat').text), float(ww_atc.find('lon').text))
				ww_frq = ww_atc.find('frequency').text
				try:
					atc.frequency = CommFrequency(ww_frq)
				except ValueError:
					atc.frequency = None
				new_ATCs.append(atc)
			self.ATCs_on_last_run = new_ATCs
			
			# Then strip data (contact claims and handover)
			for ww_flightplan in ww_root.iter('flightplan'): # NOTE the server only sends those when something changes
				ww_header = ww_flightplan.find('header')
				ww_callsign = ww_header.find('callsign').text
				ww_owner = ww_header.find('owner').text
				if ww_owner == None:
					if ww_callsign in self.current_contact_claims:
						del self.current_contact_claims[ww_callsign]
				else:
					self.current_contact_claims[ww_callsign] = ww_owner
				
				if ww_header.find('handover').text == settings.session_manager.myCallsign(): # RECEIVE A STRIP!
					strip = Strip()
					strip.writeDetail(received_from_detail, ww_owner)
					strip.writeDetail(assigned_SQ_detail, ck_int(ww_header.find('squawk').text, base=8))
					strip.writeDetail(assigned_altitude_detail, ww_header.find('assignedAlt').text)
					# Ignored from WW header above: <flags>, <assignedRunway>, <assignedRoute>, <status>, <flight>
					# Ignored from WW data below: <fuelTime>; used with ulterior motive: <pilot>
					ww_data = ww_flightplan.find('data')
					# ATC-pie hides a token in <pilot>, wake turb. on its left and callsign to its right
					# e.g. <pilot>M__ATC-pie__X-FOO</pilot> for M turb. and X-FOO strip callsign
					# If the token is absent, we know the strip is from OpenRadar
					hidden_tokens = some(ww_data.find('pilot').text, '').split(ATCpie_hidden_string, maxsplit=1)
					if len(hidden_tokens) == 1: # hidden marker NOT present; previous strip editor was OpenRadar
						strip.writeDetail(FPL.CALLSIGN, ww_callsign)
					else: # recognise strip edited with ATC-pie
						strip.writeDetail(FPL.WTC, hidden_tokens[0])
						strip.writeDetail(FPL.CALLSIGN, hidden_tokens[1])
					strip.writeDetail(FPL.FLIGHT_RULES, ww_data.find('type').text)
					strip.writeDetail(FPL.ACFT_TYPE, ww_data.find('aircraft').text)
					strip.writeDetail(FPL.ICAO_DEP, ww_data.find('departure').text)
					strip.writeDetail(FPL.ICAO_ARR, ww_data.find('destination').text)
					strip.writeDetail(FPL.ROUTE, ww_data.find('route').text)
					strip.writeDetail(FPL.CRUISE_ALT, ww_data.find('cruisingAlt').text)
					spd = ck_int(ww_data.find('trueAirspeed').text)
					if spd != None:
						strip.writeDetail(FPL.TAS, Speed(spd))
					strip.writeDetail(FPL.COMMENTS, ww_data.find('remarks').text)
					# Possibly ignored details (OpenRadar confuses FPLs and strips): DEP time, EET, alt. AD, souls [*]
					signals.receiveStrip.emit(strip)
					send_update(ww_callsign, strip) # Acknowledge strip




def ck_int(spec_string, base=10):
	try:
		return int(spec_string, base)
	except (TypeError, ValueError):
		return None



####################################

# CODE TO GET STRINGS FOR THE NON-STRIP DETAILS, IN CASE RECYCLED

## DEP time
#nsd_dep = ck_int(ww_data.find('departureTime').text)
#if nsd_dep != None:
#	dep_h = nsd_dep // 100
#	dep_min = nsd_dep % 100
#	if 0 <= dep_h < 24 and 0 <= dep_min < 60:
#		t = now().replace(hour=dep_h, minute=dep_min, second=0, microsecond=0)
#		non_strip_details.append((FPL.TIME_OF_DEP, '%s, %s' % (datestr(t), timestr(t))))

## EET
#nsd_eet = ww_data.find('estFlightTime').text
#if nsd_eet != None and ':' in nsd_eet:
#	hours, minutes = nsd_eet.split(':', maxsplit=1)
#	try:
#		non_strip_details.append((FPL.EET, '%d h %d min' % (int(hours), int(minutes))))
#	except ValueError:
#		pass

## Alternate AD
#nsd_alt = ww_data.find('alternateDest').text
#if nsd_alt:
#	non_strip_details.append((FPL.ICAO_ALT, nsd_alt))

## Soul count
#nsd_souls = ck_int(ww_data.find('soulsOnBoard').text)
#if nsd_souls:
#	non_strip_details.append((FPL.SOULS, nsd_souls))



def make_simple_element(tag, contents):
	elt = ElementTree.Element(tag)
	if contents != None:
		elt.text = str(contents)
	return elt


def make_WW_XML(fgms_id, strip, owner, handover):
	header = ElementTree.Element('header')
	data = ElementTree.Element('data')
	# Header
	header.append(make_simple_element('callsign', fgms_id))
	header.append(make_simple_element('owner', owner))
	header.append(make_simple_element('handover', handover))
	sq = strip.lookup(assigned_SQ_detail)
	header.append(make_simple_element('squawk', (None if sq == None else int('%o' % sq, base=10))))
	header.append(make_simple_element('assignedAlt', strip.lookup(assigned_altitude_detail)))
	# Ignored header
	header.append(make_simple_element('status', 'ACTIVE'))
	header.append(make_simple_element('fgcom', 'false'))
	header.append(make_simple_element('flight', None)) # WW says: element must not be empty
	header.append(make_simple_element('assignedRunway', None))
	header.append(make_simple_element('assignedRoute', None))
	# Data
	data.append(make_simple_element('type', some(strip.lookup(FPL.FLIGHT_RULES, fpl=True), 'VFR')))
	data.append(make_simple_element('aircraft', strip.lookup(FPL.ACFT_TYPE, fpl=True)))
	spd = strip.lookup(FPL.TAS, fpl=True)
	data.append(make_simple_element('trueAirspeed', (spd.kt if spd != None else None)))
	data.append(make_simple_element('departure', strip.lookup(FPL.ICAO_DEP, fpl=True)))
	data.append(make_simple_element('cruisingAlt', strip.lookup(FPL.CRUISE_ALT, fpl=True)))
	data.append(make_simple_element('route', strip.lookup(FPL.ROUTE, fpl=True)))
	data.append(make_simple_element('destination', strip.lookup(FPL.ICAO_ARR, fpl=True)))
	data.append(make_simple_element('remarks', strip.lookup(FPL.COMMENTS, fpl=True)))
	# Non-strip data for ATC-pie, but possibly given in linked flight plan
	dep = strip.lookup(FPL.TIME_OF_DEP, fpl=True)
	data.append(make_simple_element('departureTime', (None if dep == None else '%02d%02d' % (dep.hour, dep.minute))))
	eet = strip.lookup(FPL.EET, fpl=True)
	eet = None if eet == None else int(eet.total_seconds() + .5) // 60
	data.append(make_simple_element('estFlightTime', (None if eet == None else '%d:%02d' % (eet // 60, eet % 60))))
	data.append(make_simple_element('alternateDest', strip.lookup(FPL.ICAO_ALT, fpl=True)))
	data.append(make_simple_element('soulsOnBoard', strip.lookup(FPL.SOULS, fpl=True)))
	# Hidden data (ulterior motive: recognise data generated by ATC-pie)
	hidden_wake_turb = some(strip.lookup(FPL.WTC, fpl=True), '')
	hidden_callsign = some(strip.callsign(fpl=True), '')
	data.append(make_simple_element('pilot', '%s%s%s' % (hidden_wake_turb, ATCpie_hidden_string, hidden_callsign)))
	# Ignored data
	data.append(make_simple_element('fuelTime', None))
	# Wrap up
	root = ElementTree.Element('flightplan')
	root.append(header)
	root.append(data)
	return root


