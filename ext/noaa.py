from socket import timeout

from urllib.parse import urlencode
from urllib.error import URLError
from xml.etree import ElementTree

from session.config import open_URL
from data.utc import now


# ---------- Constants ----------

METAR_base_location = 'http://tgftp.nws.noaa.gov/data/observations/metar/stations'
decl_base_location = 'http://www.ngdc.noaa.gov/geomag-web/calculators/calculateDeclination'

# -------------------------------


def get_METAR(icao):
	try:
		response = open_URL('%s/%s.TXT' % (METAR_base_location, icao))
		return response.decode('ascii').split('\n')[1] + '='
	except URLError:
		print('Could not download METAR for station %s' % icao)
	except timeout:
		print('NOAA METAR request timed out.')




def get_declination(earth_location):
	today = now()
	try:
		q_items = {
			'startYear': today.year,
			'startMonth': today.month,
			'startDay': today.day,
			'resultFormat': 'xml',
			'lon1Hemisphere': 'EW'[earth_location.lon < 0],
			'lon1': abs(earth_location.lon),
			'lat1Hemisphere': 'NS'[earth_location.lat < 0],
			'lat1': abs(earth_location.lat),
			'browserRequest': 'false'
		}
		#DEBUG print('%s?%s' % (decl_base_location, urlencode(q_items)))
		response = open_URL('%s?%s' % (decl_base_location, urlencode(q_items)))
		xml = ElementTree.fromstring(response)
		if xml.tag == 'maggridresult':
			res_elt = xml.find('result')
			if res_elt != None:
				decl = float(res_elt.find('declination').text)
				return decl
	except URLError:
		print('Could not obtain declination from NOAA website.')
	except timeout:
		print('NOAA declination request timed out.')
	except ElementTree.ParseError:
		print('Parse error while reading NOAA data.')


