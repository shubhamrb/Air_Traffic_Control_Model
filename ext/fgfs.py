from telnetlib import Telnet
from PyQt5.QtCore import QProcess, QThread

from session.config import settings
from session.env import env
from ext.resources import make_FGFS_model_recognisers, make_FGFS_model_chooser
from gui.misc import signals


# ---------- Constants ----------

fgfs_viewing_acft_model = 'ufo'
dummy_viewer_callsign = 'ATC-pie'
telnet_read_timeout = 5 # seconds (or None)
initial_FOV = 55 # degrees of horizontal angle covered

ATCpie_model_string = 'ATC-pie'

FGFS_models_to_ICAO_types_file = 'resources/acft/fgfs2icao'
ICAO_types_to_FGFS_models_file = 'resources/acft/icao2fgfs'

# -------------------------------


FGFS_ACFT_recognisers, FGFS_ATC_recognisers = make_FGFS_model_recognisers(FGFS_models_to_ICAO_types_file)
FGFS_model_chooser, FGFS_model_heights, FGFS_model_liveries = make_FGFS_model_chooser(ICAO_types_to_FGFS_models_file)



def is_ATC_model(fgfs_model):
	return fgfs_model == ATCpie_model_string or any(regexp.match(fgfs_model) for regexp in FGFS_ATC_recognisers)


# FGFS model -> ICAO type identification (used when reading FGMS packets in multi-player)
def ICAO_aircraft_type(fgfs_model):
	return next((icao for regexp, icao in FGFS_ACFT_recognisers if regexp.match(fgfs_model)), fgfs_model)


# ICAO ACFT type -> FGFS model string (used to include in FGMS packets for AI traffic tower viewing)
def FGFS_model_and_height(icao_type):
	try:
		return FGFS_model_chooser[icao_type], FGFS_model_heights.get(icao_type, 0)
	except KeyError:
		return icao_type, 0








def fgTwrCommonOptions():
	assert env.airport_data != None
	pos, alt = env.viewpoint()
	options = []
	options.append('--lat=%s' % pos.lat)
	options.append('--lon=%s' % pos.lon)
	options.append('--altitude=%g' % alt)
	options.append('--heading=360')
	options.append('--aircraft=%s' % fgfs_viewing_acft_model)
	options.append('--fdm=null')
	return options



class FlightGearTowerViewer:
	def __init__(self, gui):
		self.gui = gui
		self.internal_process = QProcess(gui)
		self.internal_process.setStandardErrorFile(settings.outputFileName('fgfs-stderr', ext='log'))
		self.internal_process.stateChanged.connect(lambda state: self.notifyStartStop(state == QProcess.Running))
		self.running = False
	
	def start(self):
		weather = env.primaryWeather()
		if settings.external_tower_viewer_process:
			self.notifyStartStop(True)
			if weather != None:
				self.setWeather(weather)
		else:
			fgfs_options = fgTwrCommonOptions()
			fgfs_options.append('--roll=0')
			fgfs_options.append('--pitch=0')
			fgfs_options.append('--vc=0')
			fgfs_options.append('--fov=%g' % initial_FOV)
			# Env. options
			fgfs_options.append('--time-match-real')
			if weather == None:
				fgfs_options.append('--disable-real-weather-fetch')
			else:
				fgfs_options.append('--metar=%s' % weather.METAR()) # implies --disable-real-weather-fetch
			# Local directory options
			if settings.FGFS_root_dir != '':
				fgfs_options.append('--fg-root=%s' % settings.FGFS_root_dir)
			if settings.FGFS_aircraft_dir != '':
				fgfs_options.append('--fg-aircraft=%s' % settings.FGFS_aircraft_dir)
			if settings.FGFS_scenery_dir != '':
				fgfs_options.append('--fg-scenery=%s' % settings.FGFS_scenery_dir)
			# Connection options
			fgfs_options.append('--callsign=%s' % dummy_viewer_callsign)
			fgfs_options.append('--multiplay=out,100,localhost,%d' % settings.FGFS_views_send_port)
			fgfs_options.append('--multiplay=in,100,localhost,%d' % settings.tower_viewer_UDP_port)
			fgfs_options.append('--telnet=,,100,,%d,' % settings.tower_viewer_telnet_port)
			# Options for lightweight (interface and CPU load)
			fgfs_options.append('--disable-ai-traffic')
			fgfs_options.append('--disable-panel')
			fgfs_options.append('--disable-sound')
			fgfs_options.append('--disable-hud')
			fgfs_options.append('--disable-fullscreen')
			fgfs_options.append('--prop:/sim/menubar/visibility=false')
			# Now run
			self.internal_process.setProgram(settings.FGFS_executable)
			self.internal_process.setArguments(fgfs_options)
			#print('Running: %s %s' % (settings.FGFS_executable, ' '.join(fgfs_options)))
			self.internal_process.start()
		
	def stop(self, wait=False):
		if self.running:
			if settings.external_tower_viewer_process:
				self.notifyStartStop(False)
			else:
				self.internal_process.terminate()
				if wait:
					self.internal_process.waitForFinished() # default time-out
	
	def notifyStartStop(self, b):
			self.running = b
			signals.towerViewProcessToggled.emit(b)
	
	def sendCmd(self, cmd): # cmd can be a single command (str) or a command list
		if self.running:
			if isinstance(cmd, str):
				cmd = [cmd]
			TelnetSessionThreader(self.gui, cmd).start()
	
	# # # convenient methods for sending telnet commands
	
	def setWeather(self, weather):
		self.sendCmd('set /environment/metar/data %s' % weather.METAR())








def send_packet_to_views(udp_packet):
	if settings.controlled_tower_viewer.running:
		tower_viewer_host = settings.external_tower_viewer_host if settings.external_tower_viewer_process else 'localhost'
		send_packet_to_view(udp_packet, (tower_viewer_host, settings.tower_viewer_UDP_port))
		#print('Sent packet to %s:%d' % (tower_viewer_host, settings.tower_viewer_UDP_port))
	if settings.additional_views_active:
		for address in settings.additional_views:
			send_packet_to_view(udp_packet, address)


def send_packet_to_view(packet, addr):
	try:
		settings.FGFS_views_send_socket.sendto(packet, addr)
	except OSError as err:
		pass









class TelnetSessionThreader(QThread):
	def __init__(self, gui, commands, loopInterval=None):
		'''
		"commands" can be a list of str commands or a function (no args) that generates the list
		"loopInterval" will keep the session open and repeat it after the given timeout
		'''
		QThread.__init__(self, gui)
		self.connection = None
		self.loop_interval = loopInterval
		self.generate_commands = (lambda: commands) if isinstance(commands, list) else commands
	
	def run(self):
		try:
			tower_viewer_host = settings.external_tower_viewer_host if settings.external_tower_viewer_process else 'localhost'
			#DEBUG('Creating Telnet connection to %s:%d' % (tower_viewer_host, settings.tower_viewer_telnet_port))
			self.connection = Telnet(tower_viewer_host, port=settings.tower_viewer_telnet_port)
			self.loop = self.loop_interval != None
			self._runCommandsOnce()
			while self.loop: # set by an outside call to stop()
				QThread.msleep(self.loop_interval)
				self._runCommandsOnce()
			self.connection.close()
		except ConnectionRefusedError:
			print('Telnet connection error. Is tower view window open?')
	
	def stop(self):
		self.loop = False
	
	def _runCommandsOnce(self):
		for cmd in self.generate_commands():
			self.sendCommand(cmd)
		
	def sendCommand(self, line, answer=False):
		#DEBUGprint('Sending command: %s' % line)
		self.connection.write(line.encode('utf8') + b'\r\n')
		if answer:
			read = self.connection.read_until(b'\n', timeout=telnet_read_timeout)
			#DEBUG('Received bytes: %s' % read)
			return read.decode('utf8').strip()

