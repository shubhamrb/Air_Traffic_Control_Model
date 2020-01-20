
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtWidgets import QMessageBox

from data.util import pop_all, some
from data.comms import ChatMessage, CpdlcMessage, CommFrequency
from data.fpl import FPL
from data.utc import now
from data.weather import Weather
from data.strip import Strip, received_from_detail, handover_details

from session.config import settings
from session.env import env
from session.manager import SessionManager, SessionType, student_callsign, teacher_callsign
from session.teacher import TeachingMsg, TeachingSessionWire, CPDLC_transfer_cmd_prefix, CPDLC_message_cmd_prefix

from ext.fgfs import send_packet_to_views
from ext.fgms import update_FgmsAircraft_list

from gui.misc import signals, selection
from gui.actions import transfer_selected_or_instruct


# ---------- Constants ----------

# -------------------------------


class StudentSessionManager(SessionManager):
	def __init__(self, gui):
		SessionManager.__init__(self, gui)
		self.session_type = SessionType.STUDENT
		self.gui = gui
		self.running = False
		self.teacher_socket = QTcpSocket() # this socket connects to the teacher
		self.teacher_paused_at = None # pause time if session is paused; None otherwise
		self.traffic = [] # FgmsAircraft list
		self.known_METAR = None
	
	def start(self):
		self.teacher_socket.connectToHost(settings.teaching_service_host, settings.teaching_service_port)
		if self.teacher_socket.waitForConnected():
			env.ATCs.updateATC(teacher_callsign, None, 'Your teacher', None)
			self.teacher = TeachingSessionWire(self.teacher_socket)
			self.teacher_socket.disconnected.connect(self.disconnected)
			self.teacher.messageArrived.connect(self.receiveMsgFromTeacher)
			print('Connected to teacher.')
			self.traffic.clear()
			self.running = True
			signals.sessionStarted.emit()
		else:
			QMessageBox.critical(self.gui, 'Connection error', 'Connection to teacher has failed. Check service host and port.')
	
	def stop(self):
		if self.isRunning():
			self.running = False
			self.teacher.messageArrived.disconnect(self.receiveMsgFromTeacher)
			self.teacher_socket.disconnected.disconnect(self.disconnected)
			self.teacher_socket.disconnectFromHost()
			print('Disconnected.')
			self.traffic.clear()
			signals.sessionEnded.emit()
	
	def disconnected(self):
		QMessageBox.critical(self.gui, 'Disconnected', 'Connection error or stopped by teacher.')
		self.stop()
	
	def isRunning(self):
		return self.running
	
	def myCallsign(self):
		return student_callsign
	
	def getAircraft(self):
		return self.traffic[:]
	
	def getWeather(self, station):
		if station == settings.primary_METAR_station and self.known_METAR != None:
			return Weather(self.known_METAR)
		else:
			return None
	
	def postRadioChatMsg(self, msg):
		raise ValueError('Radio text chat disabled in student sessions. '
					'Use ATC chat to communicate with the teacher.')
	
	def postAtcChatMsg(self, msg):
		if msg.isPrivate():
			payload = '%s\n%s' % (msg.recipient(), msg.txtOnly())
			self.teacher.sendMessage(TeachingMsg(TeachingMsg.ATC_TEXT_CHAT, data=payload))
		else:
			raise ValueError('Only private messaging is enabled in tutoring sessions.')
	
	def sendCpdlcMsg(self, callsign, msg):
		self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n%s%s' % (callsign, CPDLC_message_cmd_prefix, msg.text()))))
		link = env.cpdlc.currentDataLink(callsign)
		if link != None:
			link.appendMessage(msg)
	
	def transferCpdlcAuthority(self, acft_callsign, atc_callsign):
		self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n%s%s' % (acft_callsign, CPDLC_transfer_cmd_prefix, atc_callsign))))
		env.cpdlc.endDataLink(acft_callsign, transferTo=atc_callsign)
	
	def disconnectCpdlc(self, callsign):
		self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n0' % callsign)))
		env.cpdlc.endDataLink(callsign)
	
	def instructAircraftByCallsign(self, callsign, instr):
		sugg = instr.suggestTextChatInstruction(selection.acft if callsign == selection.selectedCallsign() else None)
		signals.chatInstructionSuggestion.emit(callsign, sugg, False)
	
	
	## COMMUNICATION WITH TEACHER
	
	def receiveMsgFromTeacher(self, msg):
		#DEBUG if msg.type != TeachingMsg.TRAFFIC:#
		#DEBUG 	print('=== STUDENT RECEIVES ===\n%s\n=== End ===' % msg.data)
		if msg.type == TeachingMsg.ACFT_KILLED:
			callsign = msg.strData()
			if env.cpdlc.isConnected(callsign):
				env.cpdlc.endDataLink(callsign)
			for acft in pop_all(self.traffic, lambda a: a.identifier == callsign):
				signals.aircraftKilled.emit(acft)
		elif msg.type == TeachingMsg.TRAFFIC: # traffic update; contains FGMS packet
			fgms_packet = msg.binData()
			update_FgmsAircraft_list(self.traffic, fgms_packet)
			send_packet_to_views(fgms_packet)
			self.teacher.sendMessage(TeachingMsg(TeachingMsg.TRAFFIC))
		elif msg.type == TeachingMsg.SIM_PAUSED:
			self.teacher_paused_at = now()
			signals.sessionPaused.emit()
		elif msg.type == TeachingMsg.SIM_RESUMED:
			pause_delay = now() - self.teacher_paused_at
			for acft in self.traffic:
				acft.moveHistoryTimesForward(pause_delay)
			self.teacher_paused_at = None
			signals.sessionResumed.emit()
		elif msg.type == TeachingMsg.ATC_TEXT_CHAT:
			lines = msg.strData().split('\n')
			if len(lines) == 2:
				signals.incomingAtcTextMsg.emit(ChatMessage(lines[0], lines[1], recipient=student_callsign, private=True))
			else:
				print('ERROR: Invalid format in received ATC text chat from teacher.')
		elif msg.type == TeachingMsg.STRIP_EXCHANGE:
			line_sep = msg.strData().split('\n', maxsplit=1)
			fromATC = line_sep[0]
			strip = Strip.fromEncodedDetails('' if len(line_sep) < 2 else line_sep[1])
			strip.writeDetail(received_from_detail, fromATC)
			signals.receiveStrip.emit(strip)
		elif msg.type == TeachingMsg.SX_LIST:
			to_remove = set(env.ATCs.knownATCs())
			to_remove.discard(teacher_callsign)
			for line in msg.strData().split('\n'):
				if line != '': # last line is empty
					lst = line.rsplit('\t', maxsplit=1)
					try:
						frq = CommFrequency(lst[1]) if len(lst) == 2 else None
					except ValueError:
						frq = None
					env.ATCs.updateATC(lst[0], None, None, frq)
					to_remove.discard(lst[0])
			for atc in to_remove:
				env.ATCs.removeATC(atc)
			env.ATCs.refreshViews()
		elif msg.type == TeachingMsg.WEATHER:
			metar = msg.strData()
			station = metar.split(' ', maxsplit=1)[0]
			if station == settings.primary_METAR_station and metar != self.known_METAR:
				self.known_METAR = metar
				signals.newWeather.emit(station, Weather(metar))
		elif msg.type == TeachingMsg.PTT: # msg format: "b acft" where b is '1' or '0' for PTT on/off; acft is caller's identifier
			line_sep = msg.strData().split(' ', maxsplit=1)
			try:
				ptt = bool(int(line_sep[0]))
				caller = next(acft for acft in self.getAircraft() if acft.identifier == line_sep[1])
				if ptt:
					env.rdf.receiveSignal(caller.identifier, lambda acft=caller: acft.coords())
				else:
					env.rdf.dieSignal(caller.identifier)
			except StopIteration:
				print('Ignored PTT message from teacher (unknown ACFT %s).' % line_sep[1])
			except (ValueError, IndexError):
				print('Error decoding PTT message value from teacher')
		elif msg.type == TeachingMsg.CPDLC:
			try:
				acft_callsign, line2 = msg.strData().split('\n', maxsplit=1)
				if line2 == '0': # ACFT is disconnecting
					env.cpdlc.endDataLink(acft_callsign)
				elif line2 == '1': # ACFT is connecting (CAUTION: teacher needs confirmation of accepted connection)
					if settings.controller_pilot_data_link:
						env.cpdlc.beginDataLink(acft_callsign, student_callsign)
					self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n%d' % (acft_callsign, settings.controller_pilot_data_link))))
				elif line2.startswith(CPDLC_transfer_cmd_prefix): # ACFT being transferred to me
					if settings.controller_pilot_data_link: # CAUTION: teacher needs confirmation of accepted connection
						xfr_auth = line2[len(CPDLC_transfer_cmd_prefix):]
						env.cpdlc.beginDataLink(acft_callsign, student_callsign, transferFrom=xfr_auth)
						self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, \
								data=('%s\n%s%s' % (acft_callsign, CPDLC_transfer_cmd_prefix, xfr_auth))))
					else:
						self.teacher.sendMessage(TeachingMsg(TeachingMsg.CPDLC, data=('%s\n0' % acft_callsign)))
				elif line2.startswith(CPDLC_message_cmd_prefix): # ACFT sending a message
					encoded_msg = line2[len(CPDLC_message_cmd_prefix):]
					link = env.cpdlc.currentDataLink(acft_callsign)
					if link == None:
						print('Ignored CPDLC message sent from %s while not connected.' % acft_callsign)
					else:
						link.appendMessage(CpdlcMessage.fromText(False, encoded_msg))
				else:
					print('Error decoding CPDLC command from teacher:', line2)
			except (IndexError, ValueError):
				print('Error decoding CPDLC message value from teacher')
		else:
			print('Unhandled message type from teacher: %s' % msg.type)
	
	
	## STRIP EXCHANGE
	
	def stripDroppedOnATC(self, strip, sendto):
		msg_data = sendto + '\n' + strip.encodeDetails(handover_details)
		self.teacher.sendMessage(TeachingMsg(TeachingMsg.STRIP_EXCHANGE, data=msg_data))
		if sendto != teacher_callsign:
			transfer_selected_or_instruct(sendto)

