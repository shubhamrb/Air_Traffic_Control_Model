#!/usr/bin/env python3

#
# This file is part of the ATC-pie project,
# an air traffic control simulation program.
# 
# Copyright (C) 2015  Michael Filhol <mickybadia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

import sys
import re
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from session.config import settings, app_icon_path
from session.flightGearMP import irc_available
from gui.launcher import ATCpieLauncher, valid_location_code, min_map_range, max_map_range

from ext.sr import speech_recognition_available
from ext.tts import speech_synthesis_available
from ext.xplane import import_airfield_data, import_navaid_data, import_navfix_data, import_airway_data
from ext.resources import read_route_presets, import_entry_exit_data, \
		load_aircraft_db, load_aircraft_registration_formats, load_airlines_db


# ---------- Constants ----------

valued_option_regexp = re.compile('--([^=]+)=(.+)')

# -------------------------------


if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setWindowIcon(QIcon(app_icon_path))
	
	# Parse arguments
	try:
		location_arg = map_range_arg = None
		args = sys.argv[1:]
		while args != []:
			arg = args.pop(0)
			match = valued_option_regexp.fullmatch(arg)
			if match:
				if match.group(1) == 'map-range':
					map_range_arg = int(match.group(2))
					if not min_map_range <= map_range_arg <= max_map_range:
						raise ValueError('Map range out of bounds [%d..%d]' % (min_map_range, max_map_range))
				elif match.group(1) == 'views-send-from':
					settings.FGFS_views_send_port = int(match.group(2))
				else:
					raise ValueError('Could not interpret argument: ' + arg)
			elif location_arg == None and valid_location_code(arg):
				location_arg = arg
			else:
				raise ValueError('Bad argument: ' + arg)
		if map_range_arg != None and location_arg == None:
			raise ValueError('Map range set with no location.')
	except ValueError as err:
		sys.exit('ERROR: %s' % err)
	
	# Load global DBs
	print('Loading aircraft & airline data... ', end='', flush=True)
	load_aircraft_db()
	load_aircraft_registration_formats()
	load_airlines_db()
	print('done.')
	print('Reading world navigation & routing data... ', end='', flush=True)
	import_airfield_data()
	import_navaid_data()
	import_navfix_data()
	import_airway_data()
	import_entry_exit_data()
	print('done.')
		
	try:
		settings.FGFS_views_send_socket = socket(AF_INET, SOCK_DGRAM)
		settings.FGFS_views_send_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		settings.FGFS_views_send_socket.bind(('', settings.FGFS_views_send_port))
	except OSError as err:
		sys.exit('Socket creation error: %s' % err)
	if not irc_available:
		print('IRC library not found; multi-player ATC chat system disabled.')
	if not speech_recognition_available:
		print('Speech recognition modules not found; voice instructions disabled.')
	if not speech_synthesis_available:
		print('Speech synthesis module not found; AI pilot read-back disabled.')
	
	settings.route_presets = read_route_presets()
	settings.loadCtrRadarPositions()
	
	w = ATCpieLauncher()
	if location_arg == None:
		w.show()
	else:
		try:
			w.launch(location_arg, ctrPos=settings.CTR_radar_positions.get(location_arg, None), mapRange=map_range_arg)
		except ValueError as err:
			sys.exit('ERROR: %s' % err)
	
	exit_status = app.exec()
	settings.saveCtrRadarPositions()
	sys.exit(exit_status)


