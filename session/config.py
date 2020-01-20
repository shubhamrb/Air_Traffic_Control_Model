

import sys
from os import getpid, path
from datetime import timedelta
from xml.etree import ElementTree
from xml.dom import minidom
from urllib.request import Request, urlopen

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from data.util import some


# ---------- Constants ----------

version_string = '1.6.2'

app_icon_path = 'resources/pixmap/ATC-pie-logo.png'
FGCom_exe_dir = 'resources/fgcom'

settings_file = 'settings/settings.ini'
colour_settings_file = 'settings/colours.ini'
preset_chat_messages_file = 'settings/text-chat-messages.ini'
additional_views_file = 'settings/additional-viewers.ini'
CTR_radar_positions_file = 'settings/CTR-positions.ini'
airport_settings_filename_pattern = 'settings/ad/%s.ini'
CTR_settings_filename_pattern = 'settings/ctr/%s.ini'
output_files_dir = 'output'

default_map_range_AD = 100 # NM
default_map_range_CTR = 300 # NM

PTT_keys = [Qt.Key_Control]

default_preset_chat_messages = [
	'Please note that $icao is controlled. Contact ATC if any intentions.',
	'Go ahead.',
	'Stand by.',
	'QNH $qnh',
	'qnhg|QNH $qnhg',
	'Runways in use: $runways',
	'Wind $wind',
	'Squawk $sq',
	'Number $nseq, traffic ahead ',
	'delsid|Cleared to $dest via $wpsid departure, initial FL 100, squawk $sq, expect runway $rwydep.',
	'delvect|Cleared to $dest via vectors, initial FL 100, squawk $sq, expect runway $rwydep.',
	'rbc|Read back correct, report ready for start-up.',
	'Push-back and start-up approved, report ready to taxi.',
	'luw|Runway $rwy, line up and wait',
	'cto|Wind $wind, runway $rwy, cleared for take-off',
	'Intercept LOC, cleared ILS, report runway in sight.',
	'ctl|Wind $wind, runway $rwy, cleared to land',
	'lost|You are identified on a $qdm bearing to the airport, $dist out.',
	'?cp|Did you copy?',
	'?alt|Say altitude?',
	'?pos|Say position?',
	'?ias|Say indicated air speed?',
	'?int|Say intentions?',
	'?app|Say type of approach requested?',
	'?acft|Say type of aircraft?',
	'??radio|Are you able radio, FGCom $frq?',
	'??xpdr|Are you able transponder?',
	'??vor|Are you able VOR navigation?',
	'??taxi|Are you able to taxi?',
	'ATC service now closing at $icao. Fly safe, good bye.'
]


default_colour_specs = {
	'measuring_tool': Qt.white,
	'point_indicator': Qt.yellow,
	'RDF_line': Qt.yellow,
	'loose_strip_bay_background': '#333311', # very dark yellow
	# Radar
	'radar_background': '#050805',
	'radar_circle': '#151515',
	'radar_range_limit': Qt.darkYellow,
	# Navpoints
	'nav_fix': '#009000',
	'nav_aid': '#5555ff',
	'nav_airfield': Qt.darkRed,
	'nav_RNAV': Qt.gray,
	# Strip backgrounds
	'strip_unlinked': Qt.white,
	'strip_unlinked_identified': '#b0b0ff', # ~blue
	'strip_linked_OK': '#b0ffb0', # ~green
	'strip_linked_warning': '#ffdf83', # ~orange
	'strip_linked_alert': '#ffa0a0', # ~red
	# FPL deco icons
	'FPL_filed': Qt.black,
	'FPL_filed_outdated': Qt.gray,
	'FPL_open': Qt.green,
	'FPL_open_noETA': Qt.yellow,
	'FPL_open_overdue': Qt.red,
	'FPL_closed': Qt.darkYellow,
	# Aircraft
	'ACFT_linked': Qt.white,
	'ACFT_unlinked': '#707070',
	'ACFT_ignored': '#505050',
	'XPDR_call': '#ff0000',
	'XPDR_identification': '#2525ff',
	'selection_indicator': Qt.white,
	'assignment_OK': '#eeeeee',
	'assignment_bad': Qt.red,
	'route_followed': Qt.green,
	'route_overridden': '#aaaa00',
	'separation_ring_OK': '#707070',
	'separation_ring_warning': '#887700',
	'separation_ring_bad': '#ee3300',
	'radar_tag_line': '#404040',
	# Airport
	'AD_tarmac': '#252525',
	'AD_parking_position': '#cccc00',
	'AD_holding_lines': Qt.darkRed,
	'AD_taxiway_lines': '#555500',
	'runway': '#aaaaaa',
	'runway_reserved': '#ccff00',
	'runway_incursion': '#ff0000',
	'LDG_guide_ILS': '#3080d0',
	'LDG_guide_noILS': '#d03080',
	'ground_route_taxiway': '#cc5050',
	'ground_route_apron': '#8844aa',
	'viewpoint': Qt.white
}

# -------------------------------


def open_URL(url, postData=None, timeout=5):
	'''
	May raise urllib.request.urlopen exceptions like URLError
	'''
	req = Request(url, data=postData, headers={'User-Agent': 'ATC-pie/%s' % version_string})
	return urlopen(req, timeout=timeout).read()





class XpdrAssignmentRange:
	def __init__(self, name, lo, hi, col):
		if lo > hi:
			raise ValueError('Invalid XPDR range: %04o-%04o' % (lo, hi))
		self.name = name
		self.lo = lo
		self.hi = hi
		self.col = col









class Settings:
	'''
	Things that can/could be set by the user
	'''
	def __init__(self):
		self.run_count = 0
		self.colours = default_colour_specs
		self.preset_chat_messages = []
		self.route_presets = []
		self.CTR_radar_positions = {}
		self.additional_views = []
		self.session_manager = None
		
		self.loadPresetChatMessages()
		self.loadColourSettings()
		self.loadAdditionalViews()
		
		# Permanent between locations; only modifiable from command line
		self.FGFS_views_send_port = 5009
		self.FGFS_views_send_socket = None # not changeable from GUI
		
		# Modifiable defaults
		self._setDefaults_unsavedSettings() # to reset between locations
		self._setDefaults_systemSettings()
		self._setDefaults_localSettings()   # to reset between locations
		self._setDefaults_generalSettings()
		
		
	## ===== UNSAVED SETTINGS ===== ##
	
	def _setDefaults_unsavedSettings(self):
		# Session init.
		self.location_code = ''
		self.map_range = None
		self.first_time_at_location = True
		
		# Internal settings
		self.last_ATIS_recorded = None
		self.transmitting_radio = False
		self.MP_RDF_frequencies = {} # FGCom port -> CommFrequency
		self.teacher_ACFT_requesting_CPDLC_vectors = None
		self.session_start_sound_lock = False
		self.controlled_tower_viewer = None
		self.radar_background_images = None
		self.loose_strip_bay_backgrounds = None
		self.prepared_lexicon_file = None
		self.prepared_grammar_file = None
		
		# Run-time user options
		self.measuring_tool_logs_coordinates = False
		self.tower_height_cheat_offset = 0
		self.publicised_frequency = None
		self.additional_views_active = False
		self.FGCom_radios_silenced = False
		self.radar_cheat = False
		self.TWR_view_clear_weather_cheat = False
		self.show_recognised_voice_strings = False
		self.taxi_instructions_avoid_runways = True
		self.solo_erroneous_instruction_warning = False
		self.TTS_driver = None # FUTURE make GUI option, save & restore
		self.teacher_ACFT_touch_down_without_clearance = False
		
		# Modifiable on solo AD start only
		self.solo_role_GND = False
		self.solo_role_TWR = False
		self.solo_role_APP = False
		self.solo_role_DEP = False
	
	
	## ===== SAVED SYSTEM SETTINGS ===== ##
	
	def _setDefaults_systemSettings(self):
		# Modifiable from session start dialogs only
		self.FGMS_client_port = 5000      # FG MP only
		self.MP_IRC_enabled = True        # FG MP only
		self.MP_ORSX_enabled = True       # FG MP only
		self.teaching_service_host = ''   # student only
		self.teaching_service_port = 5000 # teacher & student
		
		# Tower viewer
		self.external_tower_viewer_process = False
		self.FGFS_executable = 'fgfs'
		self.FGFS_root_dir = '' # empty string for FlightGear default directory
		self.FGFS_aircraft_dir = '' # empty string for FlightGear default directory
		self.FGFS_scenery_dir = '' # empty string for FlightGear default directory
		self.external_tower_viewer_host = 'localhost'
		self.tower_viewer_UDP_port = 5010
		self.tower_viewer_telnet_port = 5010
		
		# For multiple session types
		self.fgcom_executable_path = path.join(FGCom_exe_dir, {'darwin': 'mac/fgcom', 'win32': 'windows/fgcom.exe'}.get(sys.platform, 'linux/fgcom'))
		self.fgcom_server = 'fgcom.flightgear.org'
		self.reserved_fgcom_port = 16665
		self.radio_fgcom_ports = list(range(16666, 16670))
		
		# FlightGear MP
		self.FGMS_server_name = 'mpserver01.flightgear.org'
		self.FGMS_server_port = 5000
		self.FGMS_legacy_protocol = False
		self.MP_social_name = ''
		self.MP_IRC_server_name = 'irc.flightgear.org'
		self.MP_IRC_server_port = 6667
		self.MP_IRC_channel = '#atc'
		self.ORSX_server_name = 'http://h2281805.stratoserver.net/FgFpServer'
		self.ORSX_handover_range = None # None = use radar range
		self.lenny64_account_email = '' # Empty string disables regular FPL checks
		self.lenny64_password_md5 = ''
		self.FPL_update_interval = timedelta(minutes=2)
		self.METAR_update_interval = timedelta(minutes=5)
		
		# Solo sessions
		self.solo_aircraft_types = ['C172', 'AT43', 'A320', 'A346', 'A388', 'B744', 'B737', 'B772', 'B773']
		self.solo_restrict_to_available_liveries = False
		self.solo_prefer_entry_exit_ADs = False
		self.sphinx_acoustic_model_dir = '' # empty string for Sphinx's default model
		self.audio_input_device_index = -1 # -1 for PyAudio default; >= 0 for manual selection
	
	
	## ===== SAVED GENERAL SETTINGS ===== ##
	
	def _setDefaults_generalSettings(self):
		# Modifiable from GUI/menus
		self.vertical_runway_box_layout = False
		self.notification_sounds_enabled = True
		self.primary_radar_active = False
		self.route_conflict_warnings = True
		self.traffic_identification_assistant = True
		self.APP_spacing_hints = False
		self.monitor_runway_occupation = False
		self.PTT_mutes_sound_notifications = True
		self.sound_notifications = None # int set (meaning depends on gui.panels.notifier) or None to be filled later
		self.general_notes = 'This notepad is saved between all sessions ' \
				'and allows to create custom general text chat aliases (see quick ref).'
		
		# Modifiable from general settings dialog
		self.strip_route_vect_warnings = True
		self.strip_CPDLC_integration = False
		self.confirm_handovers = False
		self.confirm_lossy_strip_releases = False
		self.confirm_linked_strip_deletions = True
		self.strip_autofill_on_ACFT_link = False
		self.strip_autofill_on_FPL_link = True
		self.strip_autofill_before_handovers = True
		self.strip_autolink_on_ident = False
		self.strip_autolink_include_modeC = False
		
		self.radar_contact_trace_time = timedelta(seconds=60)
		self.invisible_blips_before_contact_lost = 5
		self.radar_tag_FL_at_bottom = False
		self.radar_tag_interpret_XPDR_FL = False
		
		self.heading_tolerance = 10 # degrees
		self.altitude_tolerance = 100 # ft
		self.speed_tolerance = 15 # kt
		self.route_conflict_anticipation = timedelta(minutes=5)
		self.route_conflict_traffic = 0 # 0: exclude VFR; 1: marked IFR only; 2: all controlled traffic
		
		self.CPDLC_suggest_vector_instructions = True
		self.CPDLC_authority_transfers = True
		self.CPDLC_suggest_handover_instructions = True
		self.CPDLC_raises_windows = False
		self.CPDLC_closes_windows = False
		self.CPDLC_ACK_timeout = timedelta(seconds=20) # timedelta, or None for no timeout
		
		self.text_chat_history_time = None # timedelta, or None for no limit
		self.private_ATC_msg_auto_raise = False
		self.ATC_chatroom_msg_notifications = False
		
		# Modifiable from solo session settings dialog
		self.solo_max_aircraft_count = 6
		self.solo_min_spawn_delay = timedelta(seconds=30)
		self.solo_max_spawn_delay = timedelta(minutes=5)
		self.solo_CPDLC_balance = 0
		self.solo_distracting_traffic_count = 0
		self.solo_ARRvsDEP_balance = .33
		self.solo_ILSvsVisual_balance = 0
		self.solo_weather_change_interval = timedelta(minutes=15)
		self.solo_voice_instructions = False
		self.solo_wilco_beeps = True
		self.solo_voice_readback = False
	
	
	## ===== SAVED LOCATION-SPECIFIC SETTINGS ===== ##
	
	def _setDefaults_localSettings(self):
		# User-modifiable settings (from GUI menus, docks, etc.)
		self.selected_viewpoint = 0
		self.primary_METAR_station = ''
		self.additional_METAR_stations = []
		self.rack_colours = {}     # for racks with an assigned colour: str -> QColor
		self.ATC_collecting_racks = {} # for ATCs with an assigned receiving rack: str callsign -> str rack name
		self.auto_print_collecting_rack = None # if non-default rack collects the auto-printed strips
		self.private_racks = set() # racks excluded from who-has answers
		self.local_notes = 'This notepad is saved between sessions at this location ' \
				'and allows for custom location-specific text chat aliases (see quick ref).'
		
		# User-modifiable settings (from settings dialog)
		self.SSR_mode_capability = 'C' # possible values are '0' if SSR turned off, otherwise 'A', 'C' or 'S'
		self.radar_range = 80 # NM
		self.radar_signal_floor_level = 0 # ft ASFC (geometric)
		self.radar_sweep_interval = timedelta(seconds=5)
		self.radio_direction_finding = True
		self.controller_pilot_data_link = False
		self.auto_print_strips_include_DEP = True
		self.auto_print_strips_include_ARR = False
		self.auto_print_strips_IFR_only = False
		self.auto_print_strips_anticipation = timedelta(minutes=15)
		
		self.horizontal_separation = 5 # NM
		self.vertical_separation = 500 # ft
		self.conflict_warning_floor_FL = 80
		self.transition_altitude = 5000 # ft (useless if a TA is set in apt.dat)
		self.uncontrolled_VFR_XPDR_code = 0o7000
		self.location_radio_name = ''
		
		self.XPDR_assignment_ranges = []
		
		self.solo_APP_ceiling_FL_min = 80
		self.solo_APP_ceiling_FL_max = 120
		self.solo_TWR_ceiling_FL = 20
		self.solo_TWR_range_dist = 10
		self.solo_initial_climb_reading = 'FL100'
		self.solo_CTR_floor_FL = 200
		self.solo_CTR_ceiling_FL = 300
		self.solo_CTR_range_dist = 60
		self.solo_CTR_routing_points = [] # str list, normally of fix or navaid names
		self.solo_CTR_semi_circular_rule = 1 # i.e. SemiCircRule.E_W
		self.ATIS_custom_appendix = ''
		
		# Set once when restoring from settings; used then before closing;
		# not always in sync in between (usually manually saved by user)
		self.saved_strip_racks = []
		self.saved_strip_dock_state = {}
		self.saved_workspace_windowed_view = False
		self.saved_workspace_windows = []
	
	
	## ===== SESSIONS, RESETTING FOR NEW START-UP ===== ##
	def resetSession(self):
		self._setDefaults_unsavedSettings()
		self._setDefaults_localSettings()
		self.run_count += 1
		self.location_code = ''
	
	def sessionID(self):
		return '%d-%d' % (getpid(), self.run_count)

	def outputFileName(self, base_name, sessionID=True, ext=None):
		name = 'session-%s.' % self.sessionID() if sessionID else ''
		name += base_name
		if ext != None:
			name += '.%s' % ext
		return path.join(output_files_dir, name)
	
	
	## ===== CTR RADAR POSITIONS ===== ##
	
	def loadCtrRadarPositions(self):
		try:
			with open(CTR_radar_positions_file, encoding='utf8') as f:
				for line in f:
					tokens = line.split()
					if tokens == [] or line.startswith('#'):
						pass # Ignore empty or comment lines
					elif len(tokens) == 2:
						self.CTR_radar_positions[tokens[0]] = tokens[1]
					else:
						print('Error on CTR position spec line: %s' % line.strip())
		except FileNotFoundError:
			pass
	
	def saveCtrRadarPositions(self):
		with open(CTR_radar_positions_file, 'w', encoding='utf8') as f:
			f.write('\n'.join('%s\t%s' % (code, pos) for code, pos in self.CTR_radar_positions.items()))
	
	
	## ===== PRESET TEXT CHAT MESSAGES ===== ##
	
	def loadPresetChatMessages(self):
		try:
			with open(preset_chat_messages_file, encoding='utf8') as f:
				self.preset_chat_messages = [line.strip() for line in f.readlines() if line.strip() != '']
		except FileNotFoundError:
			self.preset_chat_messages = default_preset_chat_messages[:]
	
	def savePresetChatMessages(self):
		with open(preset_chat_messages_file, 'w', encoding='utf8') as f:
			f.write('\n'.join(self.preset_chat_messages))
	
	
	## ===== ADDITIONAL VIEWS ===== ##
	
	def loadAdditionalViews(self):
		try:
			with open(additional_views_file, encoding='utf8') as f:
				self.additional_views = []
				for line in f:
					tokens = line.split()
					if tokens == [] or line.startswith('#'):
						pass # Ignore empty or comment lines
					elif len(tokens) == 2 and tokens[1].isdigit():
						self.additional_views.append((tokens[0], int(tokens[1])))
					else:
						print('Error on viewer spec line: %s' % line.strip())
		except FileNotFoundError:
			self.additional_views = []
	
	
	## ===== COLOUR SETTINGS ===== ##
	
	def colour(self, obj):
		return QColor(self.colours[obj])
	
	def loadColourSettings(self):
		try:
			with open(colour_settings_file, encoding='utf8') as f:
				got_colours = { c:False for c in default_colour_specs }
				for line in f:
					tokens = line.split()
					if tokens == [] or line.startswith('#'):
						pass # Ignore empty or comment lines
					elif len(tokens) == 2:
						if tokens[0] in self.colours:
							self.colours[tokens[0]] = tokens[1]
							got_colours[tokens[0]] = True
						else:
							print('Unknown colour specification: %s' % tokens[0])
					else:
						print('Error on colour spec line: %s' % line.strip())
			missing = [col for col, got in got_colours.items() if not got]
			if missing != []:
				print('Missing colour specifications: %s' % ', '.join(missing))
		except FileNotFoundError:
			with open(colour_settings_file, 'w', encoding='utf8') as f:
				for obj in sorted(self.colours):
					f.write('%s\t%s\n' % (obj, QColor(self.colours[obj]).name()))
			print('Created default colour configuration file.')
	
	
	## ===== SAVING SETTINGS ===== ##
	
	def saveGeneralAndSystemSettings(self):
		root = ElementTree.Element('settings')
		
		# System settings
		root.append(xmlelt('external_tower_viewer_process', str(int(self.external_tower_viewer_process))))
		root.append(xmlelt('FGFS_executable', self.FGFS_executable))
		root.append(xmlelt('FGFS_root_dir', self.FGFS_root_dir))
		root.append(xmlelt('FGFS_aircraft_dir', self.FGFS_aircraft_dir))
		root.append(xmlelt('FGFS_scenery_dir', self.FGFS_scenery_dir))
		root.append(xmlelt('external_tower_viewer_host', self.external_tower_viewer_host))
		root.append(xmlelt('tower_viewer_UDP_port', str(self.tower_viewer_UDP_port)))
		root.append(xmlelt('tower_viewer_telnet_port', str(self.tower_viewer_telnet_port)))
		root.append(xmlelt('fgcom_executable_path', self.fgcom_executable_path))
		root.append(xmlelt('fgcom_server', self.fgcom_server))
		root.append(xmlelt('reserved_fgcom_port', str(self.reserved_fgcom_port)))
		root.append(xmllstelt('radio_fgcom_ports', self.radio_fgcom_ports, lambda p: xmlelt('radio_fgcom_port', str(p))))
		root.append(xmlelt('FGMS_server_name', self.FGMS_server_name))
		root.append(xmlelt('FGMS_server_port', str(self.FGMS_server_port)))
		root.append(xmlelt('FGMS_legacy_protocol', str(int(self.FGMS_legacy_protocol))))
		root.append(xmlelt('MP_social_name', self.MP_social_name))
		root.append(xmlelt('MP_IRC_server_name', self.MP_IRC_server_name))
		root.append(xmlelt('MP_IRC_server_port', str(self.MP_IRC_server_port)))
		root.append(xmlelt('MP_IRC_channel', self.MP_IRC_channel))
		root.append(xmlelt('ORSX_server_name', self.ORSX_server_name))
		if self.ORSX_handover_range != None:
			root.append(xmlelt('ORSX_handover_range', str(self.ORSX_handover_range)))
		root.append(xmlelt('lenny64_account_email', self.lenny64_account_email))
		root.append(xmlelt('lenny64_password_md5', self.lenny64_password_md5))
		root.append(xmlelt('FPL_update_interval', str(int(self.FPL_update_interval.total_seconds() / 60))))
		root.append(xmlelt('METAR_update_interval', str(int(self.METAR_update_interval.total_seconds() / 60))))
		root.append(xmllstelt('solo_aircraft_types', self.solo_aircraft_types, lambda t: xmlelt('aircraft_type', t)))
		root.append(xmlelt('solo_restrict_to_available_liveries', str(int(self.solo_restrict_to_available_liveries))))
		root.append(xmlelt('solo_prefer_entry_exit_ADs', str(int(self.solo_prefer_entry_exit_ADs))))
		root.append(xmlelt('sphinx_acoustic_model_dir', self.sphinx_acoustic_model_dir))
		root.append(xmlelt('audio_input_device_index', str(self.audio_input_device_index)))
		root.append(xmlelt('FGMS_client_port', str(self.FGMS_client_port)))
		root.append(xmlelt('MP_IRC_enabled', str(int(self.MP_IRC_enabled))))
		root.append(xmlelt('MP_ORSX_enabled', str(int(self.MP_ORSX_enabled))))
		root.append(xmlelt('teaching_service_host', self.teaching_service_host))
		root.append(xmlelt('teaching_service_port', str(self.teaching_service_port)))
		
		# General settings
		root.append(xmlelt('vertical_runway_box_layout', str(int(self.vertical_runway_box_layout))))
		root.append(xmlelt('notification_sounds_enabled', str(int(self.notification_sounds_enabled))))
		root.append(xmlelt('PTT_mutes_sound_notifications', str(int(self.PTT_mutes_sound_notifications))))
		root.append(xmlelt('sound_notifications', ','.join(str(n) for n in self.sound_notifications)))
		root.append(xmlelt('primary_radar_active', str(int(self.primary_radar_active))))
		root.append(xmlelt('traffic_identification_assistant', str(int(self.traffic_identification_assistant))))
		root.append(xmlelt('route_conflict_warnings', str(int(self.route_conflict_warnings))))
		root.append(xmlelt('APP_spacing_hints', str(int(self.APP_spacing_hints))))
		root.append(xmlelt('monitor_runway_occupation', str(int(self.monitor_runway_occupation))))
		root.append(xmlelt('general_notes', self.general_notes))
		
		root.append(xmlelt('strip_route_vect_warnings', str(int(self.strip_route_vect_warnings))))
		root.append(xmlelt('strip_CPDLC_integration', str(int(self.strip_CPDLC_integration))))
		root.append(xmlelt('confirm_handovers', str(int(self.confirm_handovers))))
		root.append(xmlelt('confirm_lossy_strip_releases', str(int(self.confirm_lossy_strip_releases))))
		root.append(xmlelt('confirm_linked_strip_deletions', str(int(self.confirm_linked_strip_deletions))))
		root.append(xmlelt('strip_autofill_on_ACFT_link', str(int(self.strip_autofill_on_ACFT_link))))
		root.append(xmlelt('strip_autofill_on_FPL_link', str(int(self.strip_autofill_on_FPL_link))))
		root.append(xmlelt('strip_autofill_before_handovers', str(int(self.strip_autofill_before_handovers))))
		root.append(xmlelt('strip_autolink_on_ident', str(int(self.strip_autolink_on_ident))))
		root.append(xmlelt('strip_autolink_include_modeC', str(int(self.strip_autolink_include_modeC))))
		root.append(xmlelt('radar_contact_trace_time', str(int(self.radar_contact_trace_time.total_seconds()))))
		root.append(xmlelt('invisible_blips_before_contact_lost', str(int(self.invisible_blips_before_contact_lost))))
		root.append(xmlelt('radar_tag_FL_at_bottom', str(int(self.radar_tag_FL_at_bottom))))
		root.append(xmlelt('radar_tag_interpret_XPDR_FL', str(int(self.radar_tag_interpret_XPDR_FL))))
		root.append(xmlelt('heading_tolerance', str(self.heading_tolerance)))
		root.append(xmlelt('altitude_tolerance', str(self.altitude_tolerance)))
		root.append(xmlelt('speed_tolerance', str(self.speed_tolerance)))
		root.append(xmlelt('route_conflict_anticipation', str(int(self.route_conflict_anticipation.total_seconds() / 60))))
		root.append(xmlelt('route_conflict_traffic', str(self.route_conflict_traffic)))
		
		root.append(xmlelt('CPDLC_suggest_vector_instructions', str(int(self.CPDLC_suggest_vector_instructions))))
		root.append(xmlelt('CPDLC_authority_transfers', str(int(self.CPDLC_authority_transfers))))
		root.append(xmlelt('CPDLC_suggest_handover_instructions', str(int(self.CPDLC_suggest_handover_instructions))))
		root.append(xmlelt('CPDLC_raises_windows', str(int(self.CPDLC_raises_windows))))
		root.append(xmlelt('CPDLC_closes_windows', str(int(self.CPDLC_closes_windows))))
		root.append(xmlelt('CPDLC_ACK_timeout', \
				str(0 if self.CPDLC_ACK_timeout == None else int(self.CPDLC_ACK_timeout.total_seconds()))))
		
		root.append(xmlelt('text_chat_history_time', \
				str(0 if self.text_chat_history_time == None else int(self.text_chat_history_time.total_seconds() / 60))))
		root.append(xmlelt('private_ATC_msg_auto_raise', str(int(self.private_ATC_msg_auto_raise))))
		root.append(xmlelt('ATC_chatroom_msg_notifications', str(int(self.ATC_chatroom_msg_notifications))))
		
		root.append(xmlelt('solo_max_aircraft_count', str(self.solo_max_aircraft_count)))
		root.append(xmlelt('solo_min_spawn_delay', str(int(self.solo_min_spawn_delay.total_seconds()))))
		root.append(xmlelt('solo_max_spawn_delay', str(int(self.solo_max_spawn_delay.total_seconds()))))
		root.append(xmlelt('solo_CPDLC_balance', str(self.solo_CPDLC_balance)))
		root.append(xmlelt('solo_distracting_traffic_count', str(self.solo_distracting_traffic_count)))
		root.append(xmlelt('solo_ARRvsDEP_balance', str(self.solo_ARRvsDEP_balance)))
		root.append(xmlelt('solo_ILSvsVisual_balance', str(self.solo_ILSvsVisual_balance)))
		root.append(xmlelt('solo_weather_change_interval', str(int(self.solo_weather_change_interval.total_seconds() / 60))))
		root.append(xmlelt('solo_voice_instructions', str(int(self.solo_voice_instructions))))
		root.append(xmlelt('solo_wilco_beeps', str(int(self.solo_wilco_beeps))))
		root.append(xmlelt('solo_voice_readback', str(int(self.solo_voice_readback))))
		
		with open(settings_file, 'w', encoding='utf8') as f:
			f.write(minidom.parseString(ElementTree.tostring(root)).toprettyxml()) # STYLE: generating and reparsing before writing
	
	# Local settings
	def saveLocalSettings(self, airportData):
		'''
		airportData=None for CTR mode
		'''
		root = ElementTree.Element('settings')
		
		if airportData == None:
			filename = CTR_settings_filename_pattern % self.location_code
			root.append(xmlelt('solo_CTR_floor_FL', str(self.solo_CTR_floor_FL)))
			root.append(xmlelt('solo_CTR_ceiling_FL', str(self.solo_CTR_ceiling_FL)))
			root.append(xmlelt('solo_CTR_range_dist', str(self.solo_CTR_range_dist)))
			root.append(xmlelt('solo_CTR_routing_points', ' '.join(self.solo_CTR_routing_points)))
			root.append(xmlelt('solo_CTR_semi_circular_rule', str(self.solo_CTR_semi_circular_rule)))
		else:
			filename = airport_settings_filename_pattern % self.location_code
			root.append(xmllstelt('runway_parameters', airportData.allRunways(), mk_rwy_param_elt))
			root.append(xmlelt('selected_viewpoint', str(self.selected_viewpoint)))
			
			root.append(xmlelt('solo_TWR_range_dist', str(self.solo_TWR_range_dist)))
			root.append(xmlelt('solo_TWR_ceiling_FL', str(self.solo_TWR_ceiling_FL)))
			root.append(xmlelt('solo_APP_ceiling_FL_min', str(self.solo_APP_ceiling_FL_min)))
			root.append(xmlelt('solo_APP_ceiling_FL_max', str(self.solo_APP_ceiling_FL_max)))
			root.append(xmlelt('solo_initial_climb_reading', self.solo_initial_climb_reading))
		
		root.append(xmlelt('SSR_mode_capability', self.SSR_mode_capability))
		root.append(xmlelt('radar_range', str(self.radar_range)))
		root.append(xmlelt('radar_signal_floor_level', str(self.radar_signal_floor_level)))
		root.append(xmlelt('radar_sweep_interval', str(int(self.radar_sweep_interval.total_seconds()))))
		root.append(xmlelt('radio_direction_finding', str(int(self.radio_direction_finding))))
		root.append(xmlelt('controller_pilot_data_link', str(int(self.controller_pilot_data_link))))
		root.append(xmlelt('auto_print_strips_include_DEP', str(int(self.auto_print_strips_include_DEP))))
		root.append(xmlelt('auto_print_strips_include_ARR', str(int(self.auto_print_strips_include_ARR))))
		root.append(xmlelt('auto_print_strips_IFR_only', str(int(self.auto_print_strips_IFR_only))))
		root.append(xmlelt('auto_print_strips_anticipation', str(int(self.auto_print_strips_anticipation.total_seconds() / 60))))
		
		root.append(xmlelt('horizontal_separation', str(self.horizontal_separation)))
		root.append(xmlelt('vertical_separation', str(self.vertical_separation)))
		root.append(xmlelt('conflict_warning_floor_FL', str(self.conflict_warning_floor_FL)))
		if airportData == None or airportData.transition_altitude == None:
			root.append(xmlelt('transition_altitude', str(self.transition_altitude)))
		root.append(xmlelt('uncontrolled_VFR_XPDR_code', '%04o' % self.uncontrolled_VFR_XPDR_code))
		root.append(xmlelt('location_radio_name', self.location_radio_name))
		
		root.append(xmllstelt('XPDR_ranges', self.XPDR_assignment_ranges, mk_xpdr_range_elt))
		root.append(xmlelt('ATIS_custom_appendix', self.ATIS_custom_appendix))
		
		root.append(xmlelt('primary_METAR_station', self.primary_METAR_station))
		root.append(xmllstelt('additional_METAR_stations', self.additional_METAR_stations, lambda s: xmlelt('additional_METAR_station', s)))
		root.append(xmlelt('local_notes', self.local_notes))
		root.append(xmllstelt('strip_racks', self.saved_strip_racks, \
			lambda rack: mk_rack_elt(rack, [atc for atc, collector in self.ATC_collecting_racks.items() if collector == rack])))
		root.append(mk_workspace_window_state_elt(self.saved_workspace_windowed_view, \
			self.saved_workspace_windows, self.saved_strip_dock_state))
		if self.auto_print_collecting_rack != None:
			root.append(xmlelt('auto_print_collecting_rack', self.auto_print_collecting_rack))
		with open(filename, 'w', encoding='utf8') as f:
			f.write(minidom.parseString(ElementTree.tostring(root)).toprettyxml()) # STYLE: generating and reparsing before writing
		
		
	## ===== RESTORING SETTINGS ===== ##
	
	def restoreGeneralAndSystemSettings(self):
		root = ElementTree.parse(settings_file).getroot()
		
		# System settings
		external_tower_viewer_process = root.find('external_tower_viewer_process')
		if external_tower_viewer_process != None:
			self.external_tower_viewer_process = bool(int(external_tower_viewer_process.text))
		FGFS_executable = root.find('FGFS_executable')
		if FGFS_executable != None:
			self.FGFS_executable = get_text(FGFS_executable)
		FGFS_root_dir = root.find('FGFS_root_dir')
		if FGFS_root_dir != None:
			self.FGFS_root_dir = get_text(FGFS_root_dir)
		FGFS_aircraft_dir = root.find('FGFS_aircraft_dir')
		if FGFS_aircraft_dir != None:
			self.FGFS_aircraft_dir = get_text(FGFS_aircraft_dir)
		FGFS_scenery_dir = root.find('FGFS_scenery_dir')
		if FGFS_scenery_dir != None:
			self.FGFS_scenery_dir = get_text(FGFS_scenery_dir)
		external_tower_viewer_host = root.find('external_tower_viewer_host')
		if external_tower_viewer_host != None:
			self.external_tower_viewer_host = get_text(external_tower_viewer_host)
		tower_viewer_UDP_port = root.find('tower_viewer_UDP_port')
		if tower_viewer_UDP_port != None:
			self.tower_viewer_UDP_port = int(tower_viewer_UDP_port.text)
		tower_viewer_telnet_port = root.find('tower_viewer_telnet_port')
		if tower_viewer_telnet_port != None:
			self.tower_viewer_telnet_port = int(tower_viewer_telnet_port.text)
		
		fgcom_executable_path = root.find('fgcom_executable_path')
		if fgcom_executable_path != None:
			self.fgcom_executable_path = get_text(fgcom_executable_path)
		fgcom_server = root.find('fgcom_server')
		if fgcom_server != None:
			self.fgcom_server = get_text(fgcom_server)
		reserved_fgcom_port = root.find('reserved_fgcom_port')
		if reserved_fgcom_port != None:
			self.reserved_fgcom_port = int(reserved_fgcom_port.text)
		radio_fgcom_ports = root.find('radio_fgcom_ports')
		if radio_fgcom_ports != None:
			self.radio_fgcom_ports = [int(elt.text) for elt in radio_fgcom_ports.iter('radio_fgcom_port')]
		
		FGMS_server_name = root.find('FGMS_server_name')
		if FGMS_server_name != None:
			self.FGMS_server_name = get_text(FGMS_server_name)
		FGMS_server_port = root.find('FGMS_server_port')
		if FGMS_server_port != None:
			self.FGMS_server_port = int(FGMS_server_port.text)
		FGMS_legacy_protocol = root.find('FGMS_legacy_protocol')
		if FGMS_legacy_protocol != None:
			self.FGMS_legacy_protocol = bool(int(FGMS_legacy_protocol.text)) # 0/1
		MP_social_name = root.find('MP_social_name')
		if MP_social_name != None:
			self.MP_social_name = get_text(MP_social_name)
		MP_IRC_server_name = root.find('MP_IRC_server_name')
		if MP_IRC_server_name != None:
			self.MP_IRC_server_name = get_text(MP_IRC_server_name)
		MP_IRC_server_port = root.find('MP_IRC_server_port')
		if MP_IRC_server_port != None:
			self.MP_IRC_server_port = int(MP_IRC_server_port.text)
		MP_IRC_channel = root.find('MP_IRC_channel')
		if MP_IRC_channel != None:
			self.MP_IRC_channel = get_text(MP_IRC_channel)
		ORSX_server_name = root.find('ORSX_server_name')
		if ORSX_server_name != None:
			self.ORSX_server_name = get_text(ORSX_server_name)
		ORSX_handover_range = root.find('ORSX_handover_range')
		if ORSX_handover_range != None:
			self.ORSX_handover_range = int(ORSX_handover_range.text)
		lenny64_account_email = root.find('lenny64_account_email')
		if lenny64_account_email != None:
			self.lenny64_account_email = get_text(lenny64_account_email)
		lenny64_password_md5 = root.find('lenny64_password_md5')
		if lenny64_password_md5 != None:
			self.lenny64_password_md5 = get_text(lenny64_password_md5)
		FPL_update_interval = root.find('FPL_update_interval')
		if FPL_update_interval != None:
			self.FPL_update_interval = timedelta(minutes=int(FPL_update_interval.text))
		METAR_update_interval = root.find('METAR_update_interval')
		if METAR_update_interval != None:
			self.METAR_update_interval = timedelta(minutes=int(METAR_update_interval.text))
		
		solo_aircraft_types = root.find('solo_aircraft_types')
		if solo_aircraft_types != None:
			self.solo_aircraft_types = [elt.text for elt in solo_aircraft_types.iter('aircraft_type')]
		solo_restrict_to_available_liveries = root.find('solo_restrict_to_available_liveries')
		if solo_restrict_to_available_liveries != None:
			self.solo_restrict_to_available_liveries = bool(int(solo_restrict_to_available_liveries.text)) # 0/1
		solo_prefer_entry_exit_ADs = root.find('solo_prefer_entry_exit_ADs')
		if solo_prefer_entry_exit_ADs != None:
			self.solo_prefer_entry_exit_ADs = bool(int(solo_prefer_entry_exit_ADs.text)) # 0/1
		sphinx_acoustic_model_dir = root.find('sphinx_acoustic_model_dir')
		if sphinx_acoustic_model_dir != None:
			self.sphinx_acoustic_model_dir = get_text(sphinx_acoustic_model_dir)
		audio_input_device_index = root.find('audio_input_device_index')
		if audio_input_device_index != None:
			self.audio_input_device_index = int(audio_input_device_index.text)
		
		FGMS_client_port = root.find('FGMS_client_port')
		if FGMS_client_port != None:
			self.FGMS_client_port = int(FGMS_client_port.text)
		MP_IRC_enabled = root.find('MP_IRC_enabled')
		if MP_IRC_enabled != None:
			self.MP_IRC_enabled = bool(int(MP_IRC_enabled.text)) # 0/1
		MP_ORSX_enabled = root.find('MP_ORSX_enabled')
		if MP_ORSX_enabled != None:
			self.MP_ORSX_enabled = bool(int(MP_ORSX_enabled.text)) # 0/1
		teaching_service_host = root.find('teaching_service_host')
		if teaching_service_host != None:
			self.teaching_service_host = get_text(teaching_service_host)
		teaching_service_port = root.find('teaching_service_port')
		if teaching_service_port != None:
			self.teaching_service_port = int(teaching_service_port.text)
		
		# General settings
		strip_route_vect_warnings = root.find('strip_route_vect_warnings')
		if strip_route_vect_warnings != None:
			self.strip_route_vect_warnings = bool(int(strip_route_vect_warnings.text)) # 0/1
		strip_CPDLC_integration = root.find('strip_CPDLC_integration')
		if strip_CPDLC_integration != None:
			self.strip_CPDLC_integration = bool(int(strip_CPDLC_integration.text)) # 0/1
		confirm_handovers = root.find('confirm_handovers')
		if confirm_handovers != None:
			self.confirm_handovers = bool(int(confirm_handovers.text)) # 0/1
		confirm_lossy_strip_releases = root.find('confirm_lossy_strip_releases')
		if confirm_lossy_strip_releases != None:
			self.confirm_lossy_strip_releases = bool(int(confirm_lossy_strip_releases.text)) # 0/1
		confirm_linked_strip_deletions = root.find('confirm_linked_strip_deletions')
		if confirm_linked_strip_deletions != None:
			self.confirm_linked_strip_deletions = bool(int(confirm_linked_strip_deletions.text)) # 0/1
		strip_autofill_on_ACFT_link = root.find('strip_autofill_on_ACFT_link')
		if strip_autofill_on_ACFT_link != None:
			self.strip_autofill_on_ACFT_link = bool(int(strip_autofill_on_ACFT_link.text)) # 0/1
		strip_autofill_on_FPL_link = root.find('strip_autofill_on_FPL_link')
		if strip_autofill_on_FPL_link != None:
			self.strip_autofill_on_FPL_link = bool(int(strip_autofill_on_FPL_link.text)) # 0/1
		strip_autofill_before_handovers = root.find('strip_autofill_before_handovers')
		if strip_autofill_before_handovers != None:
			self.strip_autofill_before_handovers = bool(int(strip_autofill_before_handovers.text)) # 0/1
		strip_autolink_on_ident = root.find('strip_autolink_on_ident')
		if strip_autolink_on_ident != None:
			self.strip_autolink_on_ident = bool(int(strip_autolink_on_ident.text)) # 0/1
		strip_autolink_include_modeC = root.find('strip_autolink_include_modeC')
		if strip_autolink_include_modeC != None:
			self.strip_autolink_include_modeC = bool(int(strip_autolink_include_modeC.text)) # 0/1
		
		radar_contact_trace_time = root.find('radar_contact_trace_time')
		if radar_contact_trace_time != None:
			self.radar_contact_trace_time = timedelta(seconds=int(radar_contact_trace_time.text))
		invisible_blips_before_contact_lost = root.find('invisible_blips_before_contact_lost')
		if invisible_blips_before_contact_lost != None:
			self.invisible_blips_before_contact_lost = int(invisible_blips_before_contact_lost.text)
		radar_tag_FL_at_bottom = root.find('radar_tag_FL_at_bottom')
		if radar_tag_FL_at_bottom != None:
			self.radar_tag_FL_at_bottom = bool(int(radar_tag_FL_at_bottom.text)) # 0/1
		radar_tag_interpret_XPDR_FL = root.find('radar_tag_interpret_XPDR_FL')
		if radar_tag_interpret_XPDR_FL != None:
			self.radar_tag_interpret_XPDR_FL = bool(int(radar_tag_interpret_XPDR_FL.text)) # 0/1
		heading_tolerance = root.find('heading_tolerance')
		if heading_tolerance != None:
			self.heading_tolerance = int(heading_tolerance.text)
		altitude_tolerance = root.find('altitude_tolerance')
		if altitude_tolerance != None:
			self.altitude_tolerance = int(altitude_tolerance.text)
		speed_tolerance = root.find('speed_tolerance')
		if speed_tolerance != None:
			self.speed_tolerance = int(speed_tolerance.text)
		route_conflict_anticipation = root.find('route_conflict_anticipation')
		if route_conflict_anticipation != None:
			self.route_conflict_anticipation = timedelta(minutes=int(route_conflict_anticipation.text))
		route_conflict_traffic = root.find('route_conflict_traffic')
		if route_conflict_traffic != None:
			self.route_conflict_traffic = int(route_conflict_traffic.text)
		
		CPDLC_suggest_vector_instructions = root.find('CPDLC_suggest_vector_instructions')
		if CPDLC_suggest_vector_instructions != None:
			self.CPDLC_suggest_vector_instructions = bool(int(CPDLC_suggest_vector_instructions.text)) # 0/1
		CPDLC_authority_transfers = root.find('CPDLC_authority_transfers')
		if CPDLC_authority_transfers != None:
			self.CPDLC_authority_transfers = bool(int(CPDLC_authority_transfers.text)) # 0/1
		CPDLC_suggest_handover_instructions = root.find('CPDLC_suggest_handover_instructions')
		if CPDLC_suggest_handover_instructions != None:
			self.CPDLC_suggest_handover_instructions = bool(int(CPDLC_suggest_handover_instructions.text)) # 0/1
		CPDLC_raises_windows = root.find('CPDLC_raises_windows')
		if CPDLC_raises_windows != None:
			self.CPDLC_raises_windows = bool(int(CPDLC_raises_windows.text)) # 0/1
		CPDLC_closes_windows = root.find('CPDLC_closes_windows')
		if CPDLC_closes_windows != None:
			self.CPDLC_closes_windows = bool(int(CPDLC_closes_windows.text)) # 0/1
		CPDLC_ACK_timeout = root.find('CPDLC_ACK_timeout')
		if CPDLC_ACK_timeout != None:
			value = int(CPDLC_ACK_timeout.text)
			self.CPDLC_ACK_timeout = None if value == 0 else timedelta(seconds=value)
		
		text_chat_history_time = root.find('text_chat_history_time')
		if text_chat_history_time != None:
			value = int(text_chat_history_time.text)
			self.text_chat_history_time = None if value == 0 else timedelta(minutes=value)
		private_ATC_msg_auto_raise = root.find('private_ATC_msg_auto_raise')
		if private_ATC_msg_auto_raise != None:
			self.private_ATC_msg_auto_raise = bool(int(private_ATC_msg_auto_raise.text)) # 0/1
		ATC_chatroom_msg_notifications = root.find('ATC_chatroom_msg_notifications')
		if ATC_chatroom_msg_notifications != None:
			self.ATC_chatroom_msg_notifications = bool(int(ATC_chatroom_msg_notifications.text)) # 0/1
		
		solo_max_aircraft_count = root.find('solo_max_aircraft_count')
		if solo_max_aircraft_count != None:
			self.solo_max_aircraft_count = int(solo_max_aircraft_count.text)
		solo_min_spawn_delay = root.find('solo_min_spawn_delay')
		if solo_min_spawn_delay != None:
			self.solo_min_spawn_delay = timedelta(seconds=int(solo_min_spawn_delay.text))
		solo_max_spawn_delay = root.find('solo_max_spawn_delay')
		if solo_max_spawn_delay != None:
			self.solo_max_spawn_delay = timedelta(seconds=int(solo_max_spawn_delay.text))
		solo_CPDLC_balance = root.find('solo_CPDLC_balance')
		if solo_CPDLC_balance != None:
			self.solo_CPDLC_balance = float(solo_CPDLC_balance.text)
		solo_distracting_traffic_count = root.find('solo_distracting_traffic_count')
		if solo_distracting_traffic_count != None:
			self.solo_distracting_traffic_count = int(solo_distracting_traffic_count.text)
		solo_ARRvsDEP_balance = root.find('solo_ARRvsDEP_balance')
		if solo_ARRvsDEP_balance != None:
			self.solo_ARRvsDEP_balance = float(solo_ARRvsDEP_balance.text)
		solo_ILSvsVisual_balance = root.find('solo_ILSvsVisual_balance')
		if solo_ILSvsVisual_balance != None:
			self.solo_ILSvsVisual_balance = float(solo_ILSvsVisual_balance.text)
		solo_weather_change_interval = root.find('solo_weather_change_interval')
		if solo_weather_change_interval != None:
			self.solo_weather_change_interval = timedelta(minutes=int(solo_weather_change_interval.text))
		solo_voice_instructions = root.find('solo_voice_instructions')
		if solo_voice_instructions != None:
			self.solo_voice_instructions = bool(int(solo_voice_instructions.text)) # 0/1
		solo_wilco_beeps = root.find('solo_wilco_beeps')
		if solo_wilco_beeps != None:
			self.solo_wilco_beeps = bool(int(solo_wilco_beeps.text)) # 0/1
		solo_voice_readback = root.find('solo_voice_readback')
		if solo_voice_readback != None:
			self.solo_voice_readback = bool(int(solo_voice_readback.text)) # 0/1
		
		# GUI/other settings
		general_notes = root.find('general_notes')
		if general_notes != None:
			self.general_notes = get_text(general_notes)
		vertical_runway_box_layout = root.find('vertical_runway_box_layout')
		if vertical_runway_box_layout != None:
			self.vertical_runway_box_layout = bool(int(vertical_runway_box_layout.text)) # 0/1
		notification_sounds_enabled = root.find('notification_sounds_enabled')
		if notification_sounds_enabled != None:
			self.notification_sounds_enabled = bool(int(notification_sounds_enabled.text)) # 0/1
		PTT_mutes_sound_notifications = root.find('PTT_mutes_sound_notifications')
		if PTT_mutes_sound_notifications != None:
			self.PTT_mutes_sound_notifications = bool(int(PTT_mutes_sound_notifications.text)) # 0/1
		sound_notifications = root.find('sound_notifications')
		if sound_notifications != None:
			try:
				self.sound_notifications = { int(n) for n in get_text(sound_notifications).split(',') }
			except ValueError:
				print('Could not interpret "sound_notifications" in settings.')
		primary_radar_active = root.find('primary_radar_active')
		if primary_radar_active != None:
			self.primary_radar_active = bool(int(primary_radar_active.text)) # 0/1
		traffic_identification_assistant = root.find('traffic_identification_assistant')
		if traffic_identification_assistant != None:
			self.traffic_identification_assistant = bool(int(traffic_identification_assistant.text)) # 0/1
		route_conflict_warnings = root.find('route_conflict_warnings')
		if route_conflict_warnings != None:
			self.route_conflict_warnings = bool(int(route_conflict_warnings.text)) # 0/1
		APP_spacing_hints = root.find('APP_spacing_hints')
		if APP_spacing_hints != None:
			self.APP_spacing_hints = bool(int(APP_spacing_hints.text)) # 0/1
		monitor_runway_occupation = root.find('monitor_runway_occupation')
		if monitor_runway_occupation != None:
			self.monitor_runway_occupation = bool(int(monitor_runway_occupation.text)) # 0/1
	

	def restoreLocalSettings_AD(self, airportData):
		self.location_code = airportData.navpoint.code
		root = ElementTree.parse(airport_settings_filename_pattern % self.location_code).getroot()
		self._restoreLocalSettings_shared(root)
		runway_parameters = root.find('runway_parameters')
		if runway_parameters != None:
			for rwy_elt in runway_parameters.iter('runway'):
				try:
					runway = airportData.runway(rwy_elt.attrib['name'])
				except KeyError:
					print('Ignored unnamed runway in settings file.')
				else:
					for param_elt in rwy_elt.iter('param'):
						param = param_elt.attrib['name']
						if param == 'fpa':
							runway.param_FPA = float(param_elt.text)
						elif param == 'line':
							runway.param_disp_line_length = int(param_elt.text)
						elif param == 'props':
							runway.param_acceptProps = bool(int(param_elt.text))
						elif param == 'turboprops':
							runway.param_acceptTurboprops = bool(int(param_elt.text))
						elif param == 'jets':
							runway.param_acceptJets = bool(int(param_elt.text))
						elif param == 'heavy':
							runway.param_acceptHeavy = bool(int(param_elt.text))
						else:
							print('Bad parameter spec "%s" for RWY %s' % (param, runway.name))
		
		selected_viewpoint = root.find('selected_viewpoint')
		if selected_viewpoint != None:
			self.selected_viewpoint = int(selected_viewpoint.text)
	
		solo_TWR_range_dist = root.find('solo_TWR_range_dist')
		if solo_TWR_range_dist != None:
			self.solo_TWR_range_dist = int(solo_TWR_range_dist.text)
		solo_TWR_ceiling_FL = root.find('solo_TWR_ceiling_FL')
		if solo_TWR_ceiling_FL != None:
			self.solo_TWR_ceiling_FL = int(solo_TWR_ceiling_FL.text)
		solo_APP_ceiling_FL_min = root.find('solo_APP_ceiling_FL_min')
		if solo_APP_ceiling_FL_min != None:
			self.solo_APP_ceiling_FL_min = int(solo_APP_ceiling_FL_min.text)
		solo_APP_ceiling_FL_max = root.find('solo_APP_ceiling_FL_max')
		if solo_APP_ceiling_FL_max != None:
			self.solo_APP_ceiling_FL_max = int(solo_APP_ceiling_FL_max.text)
		solo_initial_climb_reading = root.find('solo_initial_climb_reading')
		if solo_initial_climb_reading != None:
			self.solo_initial_climb_reading = solo_initial_climb_reading.text

	def restoreLocalSettings_CTR(self, location_code):
		self.location_code = location_code
		root = ElementTree.parse(CTR_settings_filename_pattern % location_code).getroot()
		self._restoreLocalSettings_shared(root)
	
		solo_CTR_floor_FL = root.find('solo_CTR_floor_FL')
		if solo_CTR_floor_FL != None:
			self.solo_CTR_floor_FL = int(solo_CTR_floor_FL.text)
		solo_CTR_ceiling_FL = root.find('solo_CTR_ceiling_FL')
		if solo_CTR_ceiling_FL != None:
			self.solo_CTR_ceiling_FL = int(solo_CTR_ceiling_FL.text)
		solo_CTR_range_dist = root.find('solo_CTR_range_dist')
		if solo_CTR_range_dist != None:
			self.solo_CTR_range_dist = int(solo_CTR_range_dist.text)
		solo_CTR_routing_points = root.find('solo_CTR_routing_points')
		if solo_CTR_routing_points != None:
			self.solo_CTR_routing_points = get_text(solo_CTR_routing_points).split()
		solo_CTR_semi_circular_rule = root.find('solo_CTR_semi_circular_rule')
		if solo_CTR_semi_circular_rule != None:
			self.solo_CTR_semi_circular_rule = int(solo_CTR_semi_circular_rule.text)
	
	def _restoreLocalSettings_shared(self, root):
		SSR_mode_capability = root.find('SSR_mode_capability')
		if SSR_mode_capability != None:
			self.SSR_mode_capability = get_text(SSR_mode_capability)
		radar_range = root.find('radar_range')
		if radar_range != None:
			self.radar_range = int(radar_range.text)
		radar_signal_floor_level = root.find('radar_signal_floor_level')
		if radar_signal_floor_level != None:
			self.radar_signal_floor_level = int(radar_signal_floor_level.text)
		radar_sweep_interval = root.find('radar_sweep_interval')
		if radar_sweep_interval != None:
			self.radar_sweep_interval = timedelta(seconds=int(radar_sweep_interval.text))
		radio_direction_finding = root.find('radio_direction_finding')
		if radio_direction_finding != None:
			self.radio_direction_finding = bool(int(radio_direction_finding.text)) # 0/1
		controller_pilot_data_link = root.find('controller_pilot_data_link')
		if controller_pilot_data_link != None:
			self.controller_pilot_data_link = bool(int(controller_pilot_data_link.text)) # 0/1
		auto_print_strips_include_DEP = root.find('auto_print_strips_include_DEP')
		if auto_print_strips_include_DEP != None:
			self.auto_print_strips_include_DEP = bool(int(auto_print_strips_include_DEP.text))
		auto_print_strips_include_ARR = root.find('auto_print_strips_include_ARR')
		if auto_print_strips_include_ARR != None:
			self.auto_print_strips_include_ARR = bool(int(auto_print_strips_include_ARR.text))
		auto_print_strips_IFR_only = root.find('auto_print_strips_IFR_only')
		if auto_print_strips_IFR_only != None:
			self.auto_print_strips_IFR_only = bool(int(auto_print_strips_IFR_only.text))
		auto_print_strips_anticipation = root.find('auto_print_strips_anticipation')
		if auto_print_strips_anticipation != None:
			self.auto_print_strips_anticipation = timedelta(minutes=int(auto_print_strips_anticipation.text))
		
		horizontal_separation = root.find('horizontal_separation')
		if horizontal_separation != None:
			self.horizontal_separation = float(horizontal_separation.text)
		vertical_separation = root.find('vertical_separation')
		if vertical_separation != None:
			self.vertical_separation = int(vertical_separation.text)
		conflict_warning_floor_FL = root.find('conflict_warning_floor_FL')
		if conflict_warning_floor_FL != None:
			self.conflict_warning_floor_FL = int(conflict_warning_floor_FL.text)
		transition_altitude = root.find('transition_altitude')
		if transition_altitude != None:
			self.transition_altitude = int(transition_altitude.text)
		uncontrolled_VFR_XPDR_code = root.find('uncontrolled_VFR_XPDR_code')
		if uncontrolled_VFR_XPDR_code != None:
			self.uncontrolled_VFR_XPDR_code = int(uncontrolled_VFR_XPDR_code.text, base=8)
		location_radio_name = root.find('location_radio_name')
		if location_radio_name != None:
			self.location_radio_name = location_radio_name.text
		
		XPDR_ranges = root.find('XPDR_ranges')
		if XPDR_ranges != None:
			for XPDR_range in XPDR_ranges.iter('XPDR_range'):
				try:
					lo = int(XPDR_range.attrib['lo'], base=8)
					hi = int(XPDR_range.attrib['hi'], base=8)
					col = XPDR_range.attrib.get('colour', None)
					colour = None if col == None else QColor(col)
					self.XPDR_assignment_ranges.append(XpdrAssignmentRange(get_text(XPDR_range), lo, hi, colour))
				except (ValueError, KeyError):
					print('Error in assignment range specification')
		ATIS_custom_appendix = root.find('ATIS_custom_appendix')
		if ATIS_custom_appendix != None:
			self.ATIS_custom_appendix = ATIS_custom_appendix.text
			
		primary_METAR_station = root.find('primary_METAR_station')
		if primary_METAR_station != None:
			self.primary_METAR_station = get_text(primary_METAR_station)
		additional_METAR_stations = root.find('additional_METAR_stations')
		if additional_METAR_stations != None:
			for additional_METAR_station in additional_METAR_stations.iter('additional_METAR_station'):
				self.additional_METAR_stations.append(get_text(additional_METAR_station))
		local_notes = root.find('local_notes')
		if local_notes != None:
			self.local_notes = get_text(local_notes)
		strip_racks = root.find('strip_racks')
		if strip_racks != None:
			for strip_rack in strip_racks.iter('strip_rack'):
				try:
					rack_name = strip_rack.attrib['name']
					if rack_name in self.saved_strip_racks:
						raise KeyError # duplicate name
				except KeyError:
					pass # No name save for this rack; ignore.
				else: # New rack to restore
					self.saved_strip_racks.append(rack_name)
					try: # COLOUR
						self.rack_colours[rack_name] = QColor(strip_rack.attrib['colour'])
					except KeyError:
						pass # No colour saved for this rack
					try: # PRIVATE?
						if bool(int(strip_rack.attrib['private'])):
							self.private_racks.add(rack_name)
					except KeyError:
						pass # Missing "private" attrib for this rack
					# COLLECTING FROM...
					for collects_from in strip_rack.iter('collects_from'):
						if collects_from.text != None and collects_from.text != '':
							self.ATC_collecting_racks[collects_from.text] = rack_name
		auto_print_collecting_rack = root.find('auto_print_collecting_rack')
		if auto_print_collecting_rack != None:
			self.auto_print_collecting_rack = auto_print_collecting_rack.text
		
		workspace_state = root.find('workspace_state')
		if workspace_state != None:
			windowed_view = workspace_state.find('windowed_view')
			if windowed_view != None:
				self.saved_workspace_windowed_view = bool(int(windowed_view.text)) # 0/1
			try:
				strip_dock = workspace_state.find('strip_dock')
				if strip_dock != None:
					self.saved_strip_dock_state = get_window_state_dict(strip_dock)
				for window in workspace_state.iter('window'):
					popped = bool(int(window.attrib['popped']))
					w_type = int(window.attrib['type'])
					state = get_window_state_dict(window)
					self.saved_workspace_windows.append((w_type, popped, state))
			except KeyError:
				print('Missing attributes for saved workspace window.')


settings = Settings()





def xmlelt(tag, text, attrib=None):
	elt = ElementTree.Element(tag)
	if text != None:
		elt.text = text
	if attrib != None:
		elt.attrib.update(attrib)
	return elt

def xmllstelt(list_tag, item_list, element_generator):
	elt = ElementTree.Element(list_tag)
	for item in item_list:
		elt.append(element_generator(item))
	return elt

def get_text(xml_element):
	return some(xml_element.text, '')

def get_window_state_dict(window_elt): # CAUTION this can raise KeyError
	res = {}
	for state in window_elt.iter('state'):
		if 'attr' in state.attrib: # single value state attribute
			res[state.attrib['attr']] = state.attrib['value']
		else:
			list_name = state.attrib['list']
			item_value = state.attrib['item']
			try:
				res[list_name].append(item_value)
			except KeyError:
				res[list_name] = [item_value]
	return res


# ------------------------------------------

def mk_rack_elt(rack_name, collects_from):
	elt = ElementTree.Element('strip_rack')
	attr = {'name': rack_name}
	if rack_name in settings.rack_colours:
		attr['colour'] = '#%X' % settings.rack_colours[rack_name].rgb()
	attr['private'] = str(int(rack_name in settings.private_racks))
	elt.attrib.update(attr)
	for atc in collects_from:
		elt.append(xmlelt('collects_from', atc))
	return elt

def mk_custom_label_elt(item):
	lbl, pos = item
	return xmlelt('custom_label', lbl, attrib={'pos': pos})

def mk_rwy_param_elt(rwy):
	params_elt = xmlelt('runway', None, attrib={'name': rwy.name})
	if not rwy.hasILS():
		params_elt.append(xmlelt('param', str(rwy.param_FPA), attrib={'name': 'fpa'}))
	params_elt.append(xmlelt('param', str(rwy.param_disp_line_length), attrib={'name': 'line'}))
	params_elt.append(xmlelt('param', str(int(rwy.param_acceptProps)), attrib={'name': 'props'}))
	params_elt.append(xmlelt('param', str(int(rwy.param_acceptTurboprops)), attrib={'name': 'turboprops'}))
	params_elt.append(xmlelt('param', str(int(rwy.param_acceptJets)), attrib={'name': 'jets'}))
	params_elt.append(xmlelt('param', str(int(rwy.param_acceptHeavy)), attrib={'name': 'heavy'}))
	return params_elt

def mk_xpdr_range_elt(rng):
	dct = {'lo': '%04o' % rng.lo, 'hi': '%04o' % rng.hi}
	if rng.col != None:
		dct['colour'] = rng.col.name()
	return xmlelt('XPDR_range', rng.name, attrib=dct)

def mk_workspace_window_state_elt(windowed_view, windows, strip_dock_state):
	res = xmlelt('workspace_state', None)
	res.append(xmlelt('windowed_view', str(int(windowed_view))))
	for window_type, window_popped, window_state in windows:
		elt = xmlelt('window', None, attrib={'type': str(window_type), 'popped': str(int(window_popped))})
		_append_window_state_elements(elt, window_state)
		res.append(elt)
	elt = xmlelt('strip_dock', None)
	_append_window_state_elements(elt, strip_dock_state)
	res.append(elt)
	return res

def _append_window_state_elements(elt, window_state):
	for attr, str_or_lst in window_state.items():
		if isinstance(str_or_lst, list):
			for value in str_or_lst:
				elt.append(xmlelt('state', None, attrib={'list': attr, 'item': value}))
		else:
			elt.append(xmlelt('state', None, attrib={'attr': attr, 'value': str_or_lst}))

