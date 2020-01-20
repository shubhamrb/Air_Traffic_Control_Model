from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QTcpServer, QHostAddress
from PyQt5.QtWidgets import QMessageBox, QInputDialog

from ai.controlled import ControlledAircraft

from data.util import pop_all
from data.fpl import FPL
from data.utc import now
from data.db import wake_turb_cat
from data.instruction import Instruction
from data.comms import ChatMessage, CpdlcMessage
from data.weather import Weather
from data.strip import Strip, handover_details, received_from_detail, sent_to_detail, \
		assigned_SQ_detail, assigned_heading_detail, assigned_altitude_detail, assigned_speed_detail

from session.config import settings
from session.env import env
from session.manager import SessionManager, SessionType, HandoverBlocked, student_callsign, teacher_callsign
from session.solo import Status, SoloParams

from ext.fgfs import send_packet_to_views
from ext.tts import speech_str2txt

from gui.misc import selection, signals, Ticker
from gui.dialog.createTraffic import CreateTrafficDialog
from gui.dialog.miscDialogs import yesNo_question


# ---------- Constants ----------

teacher_ticker_interval = 200 # ms
max_noACK_traffic = 20
new_traffic_XPDR_mode = 'C'

CPDLC_transfer_cmd_prefix = 'XFR:'
CPDLC_message_cmd_prefix = 'MSG:'

# -------------------------------



class TeachingMsg:
	msg_types = ACFT_KILLED, SIM_PAUSED, SIM_RESUMED, ATC_TEXT_CHAT, \
							STRIP_EXCHANGE, SX_LIST, WEATHER, TRAFFIC, PTT, CPDLC = range(10)
	
	def __init__(self, msg_type, data=None):
		self.type = msg_type
		self.data = b''
		if data != None:
			self.appendData(data)
	
	def appendData(self, data):
		self.data += data if isinstance(data, bytes) else data.encode('utf8')
	
	def binData(self):
		return self.data
	
	def strData(self):
		return self.data.decode('utf8')






class TeachingSessionWire(QObject):
	messageArrived = pyqtSignal(TeachingMsg)
	
	def __init__(self, socket):
		QObject.__init__(self)
		self.socket = socket
		self.got_msg_type = None
		self.got_data_len = None
		self.socket.readyRead.connect(self.readAvailableBytes)

	def readAvailableBytes(self):
		if self.got_msg_type == None:
			if self.socket.bytesAvailable() < 1:
				return
			self.got_msg_type = int.from_bytes(self.socket.read(1), 'big')
		if self.got_data_len == None:
			if self.socket.bytesAvailable() < 4:
				return
			self.got_data_len = int.from_bytes(self.socket.read(4), 'big')
		if self.socket.bytesAvailable() < self.got_data_len:
			return
		self.messageArrived.emit(TeachingMsg(self.got_msg_type, data=self.socket.read(self.got_data_len)))
		self.got_msg_type = self.got_data_len = None
		if self.socket.bytesAvailable() > 0:
			self.socket.readyRead.emit()
	
	def sendMessage(self, msg):
		#DEBUG if msg.type != TeachingMsg.TRAFFIC:
		#DEBUG 	print('Sending: %s' % msg.data)
		buf = msg.type.to_bytes(1, 'big') # message type code
		buf += len(msg.data).to_bytes(4, 'big') # length of data
		buf += msg.data # message data
		self.socket.write(buf)






# -------------------------------

class TeacherSessionManager(SessionManager):
	def __init__(self, gui):
		SessionManager.__init__(self, gui)
		self.session_type = SessionType.TEACHER
		self.gui = gui
		self.session_ticker = Ticker(self.tickSessionOnce, parent=gui)
		self.simulation_paused_at = None # pause time if session is paused; None otherwise
		self.server = QTcpServer(gui)
		self.student_socket = None
		self.server.newConnection.connect(self.studentConnects)
		self.aircraft_list = [] # ControlledAircraft list
		self.current_local_weather = None # initialised by the teaching console on sessionStarted
		self.noACK_traffic_count = 0
	
	def start(self):
		self.aircraft_list.clear()
		self.simulation_paused_at = None
		self.session_ticker.start_stopOnZero(teacher_ticker_interval)
		self.server.listen(port=settings.teaching_service_port)
		print('Teaching server ready on port %d' % settings.teaching_service_port)
		signals.specialTool.connect(self.createNewTraffic)
		signals.kbdPTT.connect(self.sendPTT)
		signals.sessionStarted.emit()
	
	def stop(self):
		if self.isRunning():
			self.session_ticker.stop()
			if self.studentConnected():
				self.shutdownStudentConnection()
			signals.specialTool.disconnect(self.createNewTraffic)
			signals.kbdPTT.disconnect(self.sendPTT)
			self.server.close()
			self.aircraft_list.clear()
			signals.sessionEnded.emit()
	
	def studentConnected(self):
		return self.student_socket != None
	
	def isRunning(self):
		return self.session_ticker.isActive() or self.simulation_paused_at != None
	
	def myCallsign(self):
		return teacher_callsign
	
	def getAircraft(self):
		return self.aircraft_list[:]
	
	def getWeather(self, station):
		return self.current_local_weather if station == settings.primary_METAR_station else None
	
	def postRadioChatMsg(self, msg):
		raise ValueError('Public radio chat panel reserved for monitoring read-backs in teacher sessions. '
					'Use the ATC text chat system to communicate with the student.')
	
	def postAtcChatMsg(self, msg):
		if self.studentConnected():
			if msg.isPrivate():
				payload = '%s\n%s' % (msg.sender(), msg.txtOnly())
				self.student.sendMessage(TeachingMsg(TeachingMsg.ATC_TEXT_CHAT, data=payload))
			else:
				raise ValueError('Only private messaging is enabled in tutoring sessions.')
		else:
			raise ValueError('No student connected.')
	
	
	## CONNECTION MANAGEMENT
	
	def studentConnects(self):
		new_connection = self.server.nextPendingConnection()
		if new_connection:
			peer_address = new_connection.peerAddress().toString()
			print('Contacted by %s' % peer_address)
			if self.studentConnected():
				new_connection.disconnectFromHost()
				print('Client rejected. Student already connected.')
			else:
				self.student_socket = new_connection
				self.student_socket.disconnected.connect(self.studentDisconnects)
				self.student_socket.disconnected.connect(self.student_socket.deleteLater)
				self.student = TeachingSessionWire(self.student_socket)
				self.student.messageArrived.connect(self.receiveMsgFromStudent)
				env.ATCs.updateATC(student_callsign, None, None, None)
				self.noACK_traffic_count = 0
				self.sendWeather()
				self.sendATCs()
				self.tickSessionOnce()
				if self.simulation_paused_at != None:
					self.student.sendMessage(TeachingMsg(TeachingMsg.SIM_PAUSED))
				QMessageBox.information(self.gui, 'Student connection', 'Student accepted from %s' % peer_address)
		else:
			print('WARNING: Connection attempt failed.')
	
	def studentDisconnects(self):
		self.shutdownStudentConnection()
		QMessageBox.information(self.gui, 'Student disconnection', 'Your student has disconnected.')
	
	def shutdownStudentConnection(self):
		self.student_socket.disconnected.disconnect(self.studentDisconnects)
		env.cpdlc.endAllDataLinks()
		env.ATCs.removeATC(student_callsign)
		self.student.messageArrived.disconnect(self.receiveMsgFromStudent)
		self.student_socket.disconnectFromHost()
		self.student_socket = None
	
	
	## TEACHER MANAGEMENT
	
	def instructAircraftByCallsign(self, callsign, instr):
		try:
			acft = next(acft for acft in self.aircraft_list if acft.identifier == callsign)
		except StopIteration:
			print('ERROR: Teacher aircraft not found: %s' % callsign)
			return
		try:
			acft.instruct([instr])
			acft.readBack([instr])
		except Instruction.Error as err:
			QMessageBox.critical(self.gui, 'Instruction error', speech_str2txt(str(err)))
	
	def createNewTraffic(self, spawn_coords, spawn_hdg):
		dialog = CreateTrafficDialog(spawn_coords, spawn_hdg, parent=self.gui)
		dialog.exec()
		if dialog.result() > 0:
			params = dialog.acftInitParams()
			params.XPDR_mode = new_traffic_XPDR_mode
			acft = ControlledAircraft(dialog.acftCallsign(), dialog.acftType(), params, None)
			acft.spawned = False
			acft.frozen = dialog.startFrozen()
			acft.tickOnce()
			self.aircraft_list.append(acft)
			if dialog.createStrip():
				strip = Strip()
				strip.writeDetail(FPL.CALLSIGN, acft.identifier)
				strip.writeDetail(FPL.ACFT_TYPE, acft.aircraft_type)
				strip.writeDetail(FPL.WTC, wake_turb_cat(acft.aircraft_type))
				strip.linkAircraft(acft)
				signals.receiveStrip.emit(strip)
			selection.selectAircraft(acft)
	
	def killAircraft(self, acft):
		if env.cpdlc.isConnected(acft.identifier):
			env.cpdlc.endDataLink(acft.identifier)
		pop_all(self.aircraft_list, lambda a: a is acft)
		if acft.spawned and self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.ACFT_KILLED, data=acft.identifier))
		signals.aircraftKilled.emit(acft)
	
	def sendATCs(self):
		if self.studentConnected():
			msg = TeachingMsg(TeachingMsg.SX_LIST)
			for atc in env.ATCs.knownATCs(lambda atc: atc.callsign != student_callsign):
				try:
					frq = env.ATCs.getATC(atc).frequency # instance of CommFrequency class, or None
				except KeyError:
					frq = None
				msg.appendData(atc if frq == None else '%s\t%s' % (atc, frq))
				msg.appendData('\n')
			self.student.sendMessage(msg)
	
	def setWeather(self, weather): # assumed at primary location and newer
		self.current_local_weather = weather
		signals.newWeather.emit(settings.primary_METAR_station, self.current_local_weather)
		self.sendWeather()
	
	def sendWeather(self):
		if self.studentConnected() and self.current_local_weather != None:
			self.student.sendMessage(TeachingMsg(TeachingMsg.WEATHER, data=self.current_local_weather.METAR()))
	
	def sendPTT(self, ignore_button, on_off):
		if selection.acft != None and selection.acft.spawned:
			if on_off:
				env.rdf.receiveSignal(selection.acft.identifier, lambda acft=selection.acft: acft.coords())
			else:
				env.rdf.dieSignal(selection.acft.identifier)
			if self.studentConnected():
				str_data = '%d %s' % (on_off, selection.acft.identifier)
				self.student.sendMessage(TeachingMsg(TeachingMsg.PTT, data=str_data))
	
	def requestCpdlcConnection(self, callsign): # NOTE: student must confirm data link
		if self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n1' % callsign)))
	
	def transferCpdlcAuthority(self, acft_callsign, atc_callsign): # for teacher, ATC here is who to transfer *from* to student
		if self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.CPDLC, \
					data=('%s\n%s%s' % (acft_callsign, CPDLC_transfer_cmd_prefix, atc_callsign)))) # NOTE: student must confirm data link
	
	def disconnectCpdlc(self, callsign):
		env.cpdlc.endDataLink(callsign)
		if self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n0' % callsign)))
	
	def sendCpdlcMsg(self, callsign, msg):
		link = env.cpdlc.currentDataLink(callsign)
		if link == None:
			return
		if msg.type() == CpdlcMessage.ACK and link.msgCount() > 0:
			last_msg = link.lastMsg()
			if not last_msg.isFromMe() and last_msg.type() == CpdlcMessage.INSTR \
					and yesNo_question(self.gui, 'ACK after received INSTR', last_msg.contents(), 'Execute instruction?'):
				try:
					instr = Instruction.fromEncodedStr(last_msg.contents())
					self.instructAircraftByCallsign(callsign, instr)
				except ValueError: # raised by Instruction.fromEncodedStr
					if not yesNo_question(self.gui, 'CPDLC comm error', \
							'Unable to decode instruction.', 'Send ACK and perform manually?'):
						return # cancel sending any message
				except Instruction.Error as err: # raised by TeacherSessionManager.instructAircraftByCallsign
					if not yesNo_question(self.gui, 'CPDLC instruction error', \
							'Unable to perform instruction: %s' % err, 'Send ACK anyway?'):
						return # cancel sending any message
				else: # no problem executing instruction
					selection.writeStripAssignment(instr)
		if self.studentConnected() and link != None:
			link.appendMessage(msg)
			self.student.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n%s%s' % (callsign, CPDLC_message_cmd_prefix, msg.text()))))
	
	def pauseSession(self):
		self.session_ticker.stop()
		self.simulation_paused_at = now()
		signals.sessionPaused.emit()
		if self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.SIM_PAUSED))
	
	def resumeSession(self):
		pause_delay = now() - self.simulation_paused_at
		for acft in self.aircraft_list:
			acft.moveHistoryTimesForward(pause_delay)
		self.simulation_paused_at = None
		self.session_ticker.start_stopOnZero(teacher_ticker_interval)
		signals.sessionResumed.emit()
		if self.studentConnected():
			self.student.sendMessage(TeachingMsg(TeachingMsg.SIM_RESUMED))
	
	
	## MESSAGES FROM STUDENT
	
	def receiveMsgFromStudent(self, msg):
		#DEBUG if msg.type != TeachingMsg.TRAFFIC:
		#DEBUG 	print('=== TEACHERS RECEIVES ===\n%s\n=== End ===' % msg.data)
		if msg.type == TeachingMsg.ATC_TEXT_CHAT:
			lines = msg.strData().split('\n')
			if len(lines) == 2:
				signals.incomingAtcTextMsg.emit(ChatMessage(student_callsign, lines[1], recipient=lines[0], private=True))
			else:
				print('ERROR: Invalid format in received ATC text chat from student.')
		elif msg.type == TeachingMsg.STRIP_EXCHANGE:
			line_sep = msg.strData().split('\n', maxsplit=1)
			toATC = line_sep[0]
			strip = Strip.fromEncodedDetails('' if len(line_sep) < 2 else line_sep[1])
			strip.writeDetail(received_from_detail, student_callsign)
			if toATC != teacher_callsign:
				strip.writeDetail(sent_to_detail, toATC)
			signals.receiveStrip.emit(strip)
		elif msg.type == TeachingMsg.WEATHER: # requesting weather information
			if msg.strData() == settings.primary_METAR_station:
				self.sendWeather()
		elif msg.type == TeachingMsg.TRAFFIC: # acknowledging a traffic message
			if self.noACK_traffic_count > 0:
				self.noACK_traffic_count -= 1
			else:
				print('ERROR: Student acknowledging unsent traffic?!')
		
		elif msg.type == TeachingMsg.CPDLC:
			# Msg format in 2 lines, first being ACFT callsign, second is either of the following:
			#  - connect/disconnect: "0" or "1"
			#  - data authority transfer: CPDLC_transfer_cmd_prefix + ATC callsign transferring to/from
			#  - other: CPDLC_message_cmd_prefix + encoded message string
			try:
				acft_callsign, line2 = msg.strData().split('\n', maxsplit=1)
				if line2 == '0': # ACFT disconnected by student
					if env.cpdlc.isConnected(acft_callsign):
						env.cpdlc.endDataLink(acft_callsign)
					else: # student is rejecting a connection (unable CPDLC)
						QMessageBox.warning(self.gui, 'CPDLC connection failed', 'Student is not accepting CPDLC connections.')
				elif line2 == '1': # student confirming ACFT log-on
					env.cpdlc.beginDataLink(acft_callsign, student_callsign)
				elif line2.startswith(CPDLC_transfer_cmd_prefix): # student transferring or confirming transfer
					atc = line2[len(CPDLC_transfer_cmd_prefix):]
					if env.cpdlc.isConnected(acft_callsign): # student initiating transfer to next ATC
						env.cpdlc.endDataLink(acft_callsign, transferTo=atc)
					else: # student confirming proposed transfer
						env.cpdlc.beginDataLink(acft_callsign, student_callsign, transferFrom=atc)
				elif line2.startswith(CPDLC_message_cmd_prefix): # student ATC sent a message
					encoded_msg = line2[len(CPDLC_message_cmd_prefix):]
					link = env.cpdlc.currentDataLink(acft_callsign)
					if link == None:
						print('Ignored CPDLC message sent to %s while not connected.' % acft_callsign)
					else:
						link.appendMessage(CpdlcMessage.fromText(False, encoded_msg))
				else:
					print('Error decoding CPDLC command from student:', line2)
			except (IndexError, ValueError):
				print('Error decoding CPDLC message value from student')
		else:
			print('ERROR: Unhandled message type from student: %s' % msg.type)
	
	
	## TICK
	
	def tickSessionOnce(self):
		pop_all(self.aircraft_list, lambda a: not env.pointInRadarRange(a.params.position))
		send_traffic_this_tick = self.studentConnected() and self.noACK_traffic_count < max_noACK_traffic
		for acft in self.aircraft_list:
			acft.tickOnce()
			fgms_packet = acft.fgmsLivePositionPacket()
			send_packet_to_views(fgms_packet)
			if send_traffic_this_tick and acft.spawned:
				self.student.sendMessage(TeachingMsg(TeachingMsg.TRAFFIC, data=fgms_packet))
				self.noACK_traffic_count += 1
	
	
	## STRIP EXCHANGE
	
	def stripDroppedOnATC(self, strip, sendto):
		if sendto == student_callsign:
			items = [teacher_callsign] + env.ATCs.knownATCs(lambda atc: atc.callsign != student_callsign)
			sender, ok = QInputDialog.getItem(self.gui, 'Send strip to student', 'Hand over strip from:', items, editable=False)
			if ok and self.studentConnected():
				msg_data = sender + '\n' + strip.encodeDetails(handover_details)
				self.student.sendMessage(TeachingMsg(TeachingMsg.STRIP_EXCHANGE, data=msg_data))
			else:
				raise HandoverBlocked('Cancelled by teacher.', silent=True)
		else:
			raise HandoverBlocked('Strips can only be sent to the student!')
	
	
	## SNAPSHOTTING
	
	def situationSnapshot(self):
		return [acft.statusSnapshot() for acft in self.aircraft_list]
	
	def restoreSituation(self, situation_snapshot):
		while self.aircraft_list != []:
			self.killAircraft(self.aircraft_list[0])
		for acft_snapshot in situation_snapshot:
			self.aircraft_list.append(ControlledAircraft.fromStatusSnapshot(acft_snapshot))
		self.tickSessionOnce()

