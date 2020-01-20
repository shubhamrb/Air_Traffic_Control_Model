from datetime import timedelta
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR

try:
	from irc.bot import SingleServerIRCBot
	irc_available = True
except ImportError:
	irc_available = False

from PyQt5.QtCore import QMutex, QThread

from data.util import pop_all, some, INET_addr_str
from data.comms import ChatMessage
from data.weather import Weather
from data.fpl import FPL, FplError
from data.utc import now
from data.strip import Strip, handover_details, received_from_detail

from session.config import settings
from session.env import env
from session.manager import SessionManager, SessionType, HandoverBlocked

from ext.fgfs import is_ATC_model
from ext.fgms import FGMShandshaker, FGMSlistener, FgmsAircraft, update_FgmsAircraft_list
from ext.orsx import WwStripExchanger
from ext.fgfs import send_packet_to_views
from ext.noaa import get_METAR
from ext.lenny64 import Lenny64Error, download_FPLs, file_new_FPL, upload_FPL_updates, set_FPL_status

from gui.actions import transfer_selected_or_instruct, answer_who_has
from gui.misc import signals, selection, Ticker


# ---------- Constants ----------

minimum_chat_message_send_count = 8
session_tick_interval = 500 # ms

IRC_auto_join_message_user_fmt = '%s connected with ATC-pie.'
IRC_auto_part_message = 'Disconnecting.'
IRC_cmd_escape_prefix = '___ATC-pie___'
IRC_cmd_strip = 'STRIP'
IRC_cmd_whohas = 'WHO_HAS'
IRC_cmd_ihave = 'I_HAVE'

# -------------------------------




# =============================================== #

#                 ONLINE CHECKERS                 #

# =============================================== #


class WeatherUpdater(QThread):
	def __init__(self, parent):
		QThread.__init__(self, parent)
		self.known_info = {} # station -> Weather
	
	def lookupOrUpdate(self, station):
		try:
			return self.known_info[station]
		except KeyError:
			self.start() # This trick works only if station is the primary or in the additional ones
		
	def run(self):
		wanted = [settings.primary_METAR_station] + settings.additional_METAR_stations
		for key in list(self.known_info): # buliding list of keys to allow deletion in loop
			if key not in wanted:
				del self.known_info[key]
		for station in wanted:
			new_metar = get_METAR(station)
			if new_metar != None:
				prev = self.known_info.get(station, None)
				self.known_info[station] = w = Weather(new_metar)
				if prev == None or w.isNewerThan(prev):
					signals.newWeather.emit(station, w)




class FPLchecker(QThread):
	def __init__(self, parent):
		QThread.__init__(self, parent)
		
	def run(self):
		try:
			day = now().date()
			online_IDs = set()
			for i in range(-4, 5):
				for online_fpl in download_FPLs(day + i * timedelta(days=1)):
					online_IDs.add(online_fpl.online_id)
					try:
						got_FPL = env.FPLs.findFPL(lambda fpl: fpl.online_id == online_fpl.online_id)[0]
					except StopIteration:
						env.FPLs.addFPL(online_fpl)
						signals.newFPL.emit(online_fpl)
					else:
						got_FPL.setOnlineStatus(online_fpl.status())
						got_FPL.setOnlineComments(online_fpl.onlineComments())
						for d in FPL.details:
							if d not in got_FPL.modified_details and got_FPL[d] != online_fpl[d]:
								got_FPL.details[d] = online_fpl[d]
			env.FPLs.clearFPLs(pred=(lambda fpl: fpl.existsOnline() and fpl.online_id not in online_IDs))
		except Lenny64Error as err:
			print('Could not check for online flight plans. %s' % err)








# ============================================== #

#                      IRC                       #

# ============================================== #

if irc_available:
	class IrcBot(SingleServerIRCBot):
		def __init__(self, IRC_nickname, cmd_callback):
			# IRC_nickname is MP callsign checked against whitespace on MP connect
			# MP social name is used here as IRC "real name"
			SingleServerIRCBot.__init__(self, [(settings.MP_IRC_server_name, settings.MP_IRC_server_port)],
					IRC_nickname, settings.MP_social_name)
			self.conn = None
			self.cmd_callback = cmd_callback
			self.expect_disconnect = False
		
		def doDisconnect(self):
			if self.conn != None:
				self.expect_disconnect = True
				self.conn.part(settings.MP_IRC_channel, message=IRC_auto_part_message)
				self.conn.disconnect(message='Disconnecting.')
		
		## REACT TO IRC EVENTS
		def on_welcome(self, server, event):
			self.expect_disconnect = False
			print('IRC connected.')
			server.join(settings.MP_IRC_channel)
		
		def on_disconnect(self, server, event):
			if not self.expect_disconnect:
				print('WARNING: IRC disconnected; retrying soon...')
		
		def on_nicknameinuse(self, server, event):
			print('WARNING: IRC nickname reported in use.')
			server.disconnect(message='Reconnecting later because of used nickname.')
		
		def on_join(self, server, event):
			if event.source.nick == settings.session_manager.myCallsign() and event.target.lower() == settings.MP_IRC_channel.lower():
				self.conn = server
				print('ATC channel joined.')
				server.privmsg(settings.MP_IRC_channel, IRC_auto_join_message_user_fmt % settings.MP_social_name)
		
		def on_pubmsg(self, server, event):
			#DEBUG('IRC: Channel msg received from %s' % event.source.nick, event.arguments[0])
			self.process_message(ChatMessage(event.source.nick, event.arguments[0], private=False))
		
		def on_privmsg(self, server, event):
			#DEBUG('IRC: Private msg received from %s' % event.source.nick, event.arguments[0])
			msg = ChatMessage(event.source.nick, event.arguments[0],
					recipient=settings.session_manager.myCallsign(), private=True)
			self.process_message(msg)
		
		
		## SEND/RECEIVE MESSAGES
		def send_privmsg(self, target, text):
			if self.conn == None:
				raise ValueError('IRC connection lost or not yet available.')
			else:
				self.conn.privmsg(target, text)
		
		def process_message(self, msg):
			msg_line = msg.txtOnly()
			if msg_line.startswith(IRC_cmd_escape_prefix): # Process escaped ATC-pie command
				escaped_split = msg_line[len(IRC_cmd_escape_prefix):].split(' ', maxsplit=2)
				if len(escaped_split) < 2:
					print('Truncated or illegal escaped line received by IRC bot: %s' % msg_line)
				else: # length is 2 or 3
					key = escaped_split[0]
					cmd = escaped_split[1]
					argstr = '' if len(escaped_split) == 2 else escaped_split[2]
					self.cmd_callback(msg.sender(), key, msg.isPrivate(), cmd, argstr)
			else: # incoming non-escaped message (private or channel message)
				signals.incomingAtcTextMsg.emit(msg)



class IrcCommunicator(QThread):
	def __init__(self, gui, IRC_nickname):
		QThread.__init__(self, gui)
		self.bot = IrcBot(IRC_nickname, self.receiveCmdMsg)
		self.gui = gui
		self.cmd_counter = 0
		
	def run(self):
		#DEBUG print('Connecting to IRC server.')
		self.bot.start()
	
	def stopAndWait(self):
		self.bot.doDisconnect()
		self.usleep(100)
		self.terminate()
		self.wait()
	
	def isConnected(self, atc_callsign):
		return self.bot.channels[settings.MP_IRC_channel].has_user(atc_callsign)
	
	def sendChatMsg(self, msg):
		if msg.isPrivate():
			self.bot.send_privmsg(msg.recipient(), msg.txtOnly()) # may raise ValueError
		else:
			self.bot.send_privmsg(settings.MP_IRC_channel, msg.txtMsg()) # may raise ValueError
	
	def sendCmdMsg(self, cmd, argstr, privateTo=None):
		'''
		Returns a unique key for the sent command (useful to store if an acknowledgement is expected).
		'''
		ack_key = str(self.cmd_counter)
		text_to_send = '%s%s %s %s' % (IRC_cmd_escape_prefix, ack_key, cmd, argstr)
		self.bot.send_privmsg(some(privateTo, settings.MP_IRC_channel), text_to_send) # may raise ValueError
		self.cmd_counter += 1
		return ack_key
	
	def receiveCmdMsg(self, sender, ack_key, private, cmd, argstr):
		if private and cmd == IRC_cmd_strip:
			strip = Strip.fromEncodedDetails(argstr) # may raise ValueError
			strip.writeDetail(received_from_detail, sender)
			signals.receiveStrip.emit(strip)
		elif cmd == IRC_cmd_whohas: # whether private or not
			if answer_who_has(argstr):
				self.sendCmdMsg(IRC_cmd_ihave, argstr, privateTo=sender)
		elif cmd == IRC_cmd_ihave: # whether private or not
			signals.incomingContactClaim.emit(sender, argstr)
		else:
			print('WARNING: Ignoring unrecognised/illegal IRC escaped command "%s" from %s' % (cmd, sender))



# ============================================= #

#                SESSION MANAGER                #

# ============================================= #

class FlightGearMultiPlayerSessionManager(SessionManager):
	def __init__(self, gui, callsign):
		SessionManager.__init__(self, gui)
		self.session_type = SessionType.FLIGHTGEAR_MP
		self.has_online_FPLs = True
		self.my_callsign = callsign
		self.socket = None # None here when simulation NOT running
		self.session_ticker = Ticker(self.sessionTick, parent=gui)
		self.IRC_communicator = IrcCommunicator(gui, callsign) if irc_available and settings.MP_IRC_enabled else None
		self.WW_strip_exchanger = WwStripExchanger(gui)
		self.connection_list_mutex = QMutex() # Critical: session ticker clearing zombies vs. FGMS listener adding traffic
		self.weather_updater = WeatherUpdater(gui)
		self.FPL_checker = FPLchecker(gui)
		self.FPL_checker.finished.connect(env.FPLs.refreshViews)
		self.FPL_ticker = Ticker(self.FPL_checker.start, parent=gui)
		self.METAR_ticker = Ticker(self.weather_updater.start, parent=gui)
		self.FGMS_connections = [] # FgmsAircraft list of "connected" FGMS callsigns
	
	def start(self):
		try:
			self.socket = socket(AF_INET, SOCK_DGRAM)
			self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
			self.socket.bind(('', settings.FGMS_client_port))
			self.server_address = settings.FGMS_server_name, settings.FGMS_server_port
		except OSError as error:
			self.socket = None
			print('Connection error: %s' % error)
		else:
			self.chat_msg_send_count = 0
			self.chat_msg_queue = [] # pop first, enqueue at end
			self.FGMS_handshaker = FGMShandshaker(self.gui, self.socket, self.server_address, self.myCallsign())
			self.session_ticker.start(session_tick_interval)
			self.FGMS_listener = FGMSlistener(self.gui, self.socket, self.receiveFgmsData)
			self.FGMS_listener.start()
			if self.IRC_communicator != None:
				self.IRC_communicator.start()
			if settings.MP_ORSX_enabled:
				self.WW_strip_exchanger.start()
			self.FPL_ticker.start_stopOnZero(settings.FPL_update_interval)
			self.METAR_ticker.start_stopOnZero(settings.METAR_update_interval)
			signals.fplUpdateRequest.connect(self.FPL_checker.start)
			signals.weatherUpdateRequest.connect(self.weather_updater.start)
			signals.sessionStarted.emit()
			print('Connected local port %d to %s.' % \
					(settings.FGMS_client_port, INET_addr_str(settings.FGMS_server_name, settings.FGMS_server_port)))
	
	def stop(self):
		if self.isRunning():
			signals.fplUpdateRequest.disconnect(self.FPL_checker.start)
			signals.weatherUpdateRequest.disconnect(self.weather_updater.start)
			# stop tickers and threads in a clean way
			self.FGMS_listener.stop() # looping thread
			self.session_ticker.stop() # ticker triggering a one shot thread
			self.FPL_ticker.stop() # ticker triggering a one shot thread
			self.METAR_ticker.stop() # ticker triggering a one shot thread
			if self.IRC_communicator != None:
				self.IRC_communicator.stopAndWait()
			self.WW_strip_exchanger.stopAndWait()
			for thread in self.FGMS_listener, self.FGMS_handshaker, self.FPL_checker, self.weather_updater:
				thread.wait()
			del self.FGMS_handshaker
			del self.FGMS_listener
			# finish up
			self.socket = None
			self.FGMS_connections.clear()
			signals.sessionEnded.emit()
	
	def isRunning(self):
		return self.socket != None
	
	def myCallsign(self):
		return self.my_callsign
	
	def getAircraft(self):
		self.connection_list_mutex.lock()
		result = [acft for acft in self.FGMS_connections if not is_ATC_model(acft.aircraft_type)]
		self.connection_list_mutex.unlock()
		return result
	
	def getWeather(self, station):
		# Returns the weather straight away if known, otherwise answers None but triggers the updater
		# which will signal the new weather if station is the primary or a registered additional station
		return self.weather_updater.lookupOrUpdate(station)
	
	def postRadioChatMsg(self, msg):
		txt = msg.txtMsg()
		if txt == (self.FGMS_handshaker.currentChatMessage() if self.chat_msg_queue == [] else self.chat_msg_queue[-1]):
			raise ValueError('FGMS ignores a text message if it is identical to the previous.')
		else:
			self.chat_msg_queue.append(txt)
	
	def instructAircraftByCallsign(self, callsign, instr):
		sugg = instr.suggestTextChatInstruction(selection.acft if callsign == selection.selectedCallsign() else None)
		signals.chatInstructionSuggestion.emit(callsign, sugg, False)
	
	
	## CPDLC
	
	def sendCpdlcMsg(self, callsign, msg):
		print('FUTURE: implement sendCpdlcMsg', callsign, msg.type())
	
	def transferCpdlcAuthority(self, acft_callsign, atc_callsign):
		print('FUTURE: implement transferCpdlcAuthority', acft_callsign, atc_callsign)
	
	def disconnectCpdlc(self, callsign):
		print('FUTURE: implement disconnectCpdlc')
	
	
	## FPLs
	
	def pushFplOnline(self, fpl):
		if settings.lenny64_account_email == '':
			raise FplError('No Lenny64 account provided. Fill in MP system settings.')
		try:
			if fpl.existsOnline():
				upload_FPL_updates(fpl)
			else:
				file_new_FPL(fpl)
			env.FPLs.refreshViews()
		except Lenny64Error as err:
			msg = 'A problem occured while uploading FPL data. Are you missing mandatory details?'
			if err.srvResponse() != None:
				msg += '\nCheck console output for full server response.'
				print('Lenny64 server response: %s' % err.srvResponse())
			raise FplError(msg)
	
	def changeFplStatus(self, fpl, new_status):
		if self.isRunning() and settings.lenny64_account_email != '':
			try:
				set_FPL_status(fpl, new_status)
			except Lenny64Error as err:
				msg = 'Error in setting FPL online status (ID = %s): %s' % (fpl.online_id, err)
				if err.srvResponse() != None:
					msg += '\nServer response was: %s' % err.srvResponse()
				print(msg)
			else:
				env.FPLs.refreshViews()
	
	
	## ATCs and STRIP EXCHANGE
	
	def postAtcChatMsg(self, msg):
		if self.IRC_communicator == None:
			raise ValueError('ATC text chat disabled. Reconnect to enable from start dialog.')
		elif msg.txtOnly().startswith(IRC_cmd_escape_prefix):
			raise ValueError('ATC-pie cannot send messages starting with "%s"' % IRC_cmd_escape_prefix)
		elif msg.isPrivate() and not self.IRC_communicator.isConnected(msg.recipient()):
			raise ValueError('User unreachable through this channel.')
		else:
			self.IRC_communicator.sendChatMsg(msg) # can raise ValueError
	
	def stripDroppedOnATC(self, strip, atc_callsign):
		if strip.linkedAircraft() != None and self.WW_strip_exchanger.isConnected(atc_callsign): # implies isRunning()
			self.WW_strip_exchanger.handOver(strip, atc_callsign) # raises HandoverBlocked if not allowed/possible
		elif self.IRC_communicator != None and self.IRC_communicator.isConnected(atc_callsign):
			self.IRC_communicator.sendCmdMsg(IRC_cmd_strip, strip.encodeDetails(handover_details), privateTo=atc_callsign)
		else:
			raise HandoverBlocked('No common sub-system available for strip exchange with this user.')
		transfer_selected_or_instruct(atc_callsign)
	
	def sendWhoHas(self, callsign):
		if self.IRC_communicator != None:
			self.IRC_communicator.sendCmdMsg(IRC_cmd_whohas, callsign)
		ww_claim = self.WW_strip_exchanger.claimingContact(callsign)
		if ww_claim != None:
			signals.incomingContactClaim.emit(ww_claim, callsign)
		
	
	
	## FGMS
	
	def sessionTick(self):
		if self.chat_msg_send_count >= minimum_chat_message_send_count and self.chat_msg_queue != []:
			self.chat_msg_send_count = 0
			self.FGMS_handshaker.setChatMessage(self.chat_msg_queue.pop(0))
		self.FGMS_handshaker.start()
		self.chat_msg_send_count += 1
		self.connection_list_mutex.lock()
		pop_all(self.FGMS_connections, FgmsAircraft.isZombie)
		# update ATC model before unlocking mutex
		old_register = env.ATCs.knownATCs()
		updated = []
		for atc in self.WW_strip_exchanger.connectedATCs():
			env.ATCs.updateATC(atc.callsign, atc.position, atc.social_name, atc.frequency)
			updated.append(atc.callsign)
		for c in self.FGMS_connections:
			if is_ATC_model(c.aircraft_type) and c.identifier not in updated:
				env.ATCs.updateATC(c.identifier, c.liveCoords(), c.ATCpie_social_name, c.ATCpie_publicised_frequency)
				updated.append(c.identifier)
		for had_callsign in old_register:
			if had_callsign not in updated:
				env.ATCs.removeATC(had_callsign)
		self.connection_list_mutex.unlock()
		env.ATCs.refreshViews()
	
	def receiveFgmsData(self, udp_packet):
		self.connection_list_mutex.lock()
		update_FgmsAircraft_list(self.FGMS_connections, udp_packet)
		self.connection_list_mutex.unlock()
		send_packet_to_views(udp_packet)
	

