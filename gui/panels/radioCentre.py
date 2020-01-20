
from os import path
from socket import socket, AF_INET, SOCK_DGRAM

from PyQt5.QtWidgets import QWidget, QDialog, QInputDialog, QMessageBox, QMenu, QAction
from PyQt5.QtCore import QProcess, pyqtSignal

from ui.radiobox import Ui_radioBox
from ui.radios import Ui_radioCentrePane
from ui.fgcomEchoTestDialog import Ui_fgcomEchoTestDialog
from ui.recordAtisDialog import Ui_recordAtisDialog

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.util import some
from data.comms import CommFrequency, replace_text_aliases
from data.nav import Navpoint, world_navpoint_db

from gui.misc import Ticker, signals, selection


# ---------- Constants ----------

soft_sound_level = .25
loud_sound_level = 1
fgcom_controller_ticker_interval = 500 # in seconds
frequencies_always_proposed = [(CommFrequency(123.5), 'Unicom'), \
		(CommFrequency(121.5), 'EMG'), (CommFrequency(122.75), 'FG A/A 1'), (CommFrequency(123.45), 'FG A/A 2')]

# -------------------------------



def FGCom_callsign():
	cs = settings.session_manager.myCallsign()
	if settings.session_manager.session_type in [SessionType.TEACHER, SessionType.STUDENT]:
		cs += '_' + settings.location_code
	return cs



class InternalFgcomInstance(QProcess):
	def __init__(self, port, cmdopts, parent):
		QProcess.__init__(self, parent)
		cmdopts.append('--server=%s' % settings.fgcom_server)
		cmdopts.append('--port=%d' % port)
		cmdopts.append('--callsign=%s' % FGCom_callsign())
		abs_exe_path = path.abspath(settings.fgcom_executable_path)
		self.setWorkingDirectory(path.dirname(abs_exe_path))
		self.setProgram(abs_exe_path)
		self.setArguments(cmdopts)
		self.setStandardErrorFile(settings.outputFileName('fgcom-stderr-port%d' % port, ext='log'))
		#DEBUG print('FGCom command: %s %s' % (abs_exe_path, ' '.join(cmdopts)))
	


class FgcomSettings:
	def __init__(self, socket, address):
		self.socket = socket
		self.address = address
		try:
			self.frq = env.frequencies[0][0]
		except IndexError:
			self.frq = frequencies_always_proposed[0][0]
		self.ptt = False  # "push to talk"
		self.vol = 1      # output volume
		pos = env.radarPos()
		# packet format has 3 slots to fill: PTT, frq, vol
		self.packet_format = 'PTT=%d'
		self.packet_format += ',LAT=%f,LON=%f,ALT=%f' % (pos.lat, pos.lon, env.elevation(pos))
		self.packet_format += ',COM1_FRQ=%s,COM2_FRQ=121.850'
		self.packet_format += ',OUTPUT_VOL=%f,SILENCE_THD=-60'
		self.packet_format += ',CALLSIGN=%s' % FGCom_callsign()

	def send(self):
		packet_str = self.packet_format % (self.ptt, self.frq, self.vol)
		self.socket.sendto(bytes(packet_str, 'utf8'), self.address)




class RadioBox(QWidget, Ui_radioBox):
	def __init__(self, parent, external, port):
		'''
		external is a host (possibly localhost) for external FGCom instance, or None for internal (child process)
		'''
		QWidget.__init__(self, parent)
		self.setupUi(self)
		client_address = some(external, 'localhost'), port
		self.settings = FgcomSettings(socket(AF_INET, SOCK_DGRAM), client_address)
		self.controller = Ticker(self.settings.send, parent=self)
		self.frequency_combo.addFrequencies([(frq, descr) for frq, descr, t in env.frequencies])
		self.frequency_combo.addFrequencies(frequencies_always_proposed)
		if external == None: # child process
			self.onOff_button.setToolTip('Internal FGCom instance using local port %d' % port)
			ad = world_navpoint_db.findClosest(env.radarPos(), types=[Navpoint.AD]).code if env.airport_data == None else settings.location_code
			self.instance = InternalFgcomInstance(port, ['--airport=%s' % ad], self)
			self.instance.started.connect(self.processHasStarted)
			self.instance.finished.connect(self.processHasStopped)
			self.onOff_button.toggled.connect(self.switchFGCom)
		else: # creating box for external instance
			self.instance = None
			self.onOff_button.setToolTip('External FGCom instance on %s:%d' % client_address)
			self.onOff_button.setChecked(True) # keep checked (tested for RDF)
			self.onOff_button.setEnabled(False)
			self.PTT_button.setEnabled(True)
			self.controller.start(fgcom_controller_ticker_interval)
		self.PTT_button.pressed.connect(lambda: self.PTT(True))
		self.PTT_button.released.connect(lambda: self.PTT(False))
		self.softVolume_tickBox.clicked.connect(self.setVolume)
		self.frequency_combo.frequencyChanged.connect(self.setFrequency)
		self.updateRDF()
		self.RDF_tickBox.toggled.connect(self.updateRDF)
		self.onOff_button.toggled.connect(self.updateRDF)
		signals.localSettingsChanged.connect(self.updateRDF)
	
	def isInternal(self):
		return self.instance != None
	
	def clientAddress(self):
		return self.settings.address
	
	def getReadyForRemoval(self):
		if self.isInternal():
			self.switchFGCom(False)
			self.instance.waitForFinished(1000)
		else:
			self.controller.stop()
		try:
			del settings.MP_RDF_frequencies[self.settings.address[1]]
		except KeyError:
			pass
	
	def setVolume(self):
		if settings.FGCom_radios_muted:
			self.settings.vol = 0
		elif self.softVolume_tickBox.isChecked():
			self.settings.vol = soft_sound_level
		else:
			self.settings.vol = loud_sound_level
		self.settings.send()
		
	def setFrequency(self, frq):
		self.PTT(False)
		self.settings.frq = frq
		self.updateRDF()
		self.settings.send()
	
	def PTT(self, toggle):
		self.settings.ptt = toggle
		self.PTT_button.setChecked(toggle and self.PTT_button.isEnabled())
		# NOTE: line below is unreliable on mouse+kbd mix, but not a serious problem.
		settings.transmitting_radio = toggle # accounts for direct mouse PTT press
		self.settings.send()
	
	def updateRDF(self):
		frq_select_available = settings.radio_direction_finding and settings.session_manager.session_type == SessionType.FLIGHTGEAR_MP
		self.RDF_tickBox.setEnabled(frq_select_available)
		box_key = self.settings.address[1]
		if frq_select_available and self.RDF_tickBox.isChecked():
			settings.MP_RDF_frequencies[box_key] = self.settings.frq
		else:
			try:
				del settings.MP_RDF_frequencies[box_key]
			except KeyError:
				pass
	
	
	## Controlling FGCom process
	
	def switchFGCom(self, on_off):
		if self.isInternal():
			self.removeBox_button.setEnabled(not on_off)
		if on_off: # Start FGCom
			self.instance.start()
		else: # Stop FGCom
			self.PTT(False)
			self.instance.kill()
	
	def processHasStarted(self):
		self.PTT_button.setEnabled(True)
		self.controller.start(fgcom_controller_ticker_interval)
	
	def processHasStopped(self, exit_code, status):
		self.controller.stop()
		self.PTT_button.setEnabled(False)
		self.PTT_button.setChecked(False)
		self.onOff_button.setChecked(False)
	








class EchoTestDialog(QDialog, Ui_fgcomEchoTestDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.instance = InternalFgcomInstance(settings.reserved_fgcom_port, ['--frequency=910.000'], self)
		self.OK_button.clicked.connect(self.closeMe)
		self.instance.started.connect(self.processHasStarted)
		self.instance.finished.connect(self.processHasStopped)
		self.instance.start()
		#print('Executed: %s %s' % (self.instance.program(), ' '.join(self.instance.arguments())))
	
	def processHasStopped(self):
		self.label.setText('FGCom has stopped.')
	
	def processHasStarted(self):
		self.label.setText('Hearing echo?')
	
	def closeMe(self):
		if self.instance.state() == QProcess.Running:
			self.instance.kill()
		self.accept()








class RecordAtisDialog(QDialog, Ui_recordAtisDialog):
	def __init__(self, frequency, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		cmdopts = ['--airport=%s' % settings.location_code, '--atis=%s' % frequency]
		self.recorded = False
		if settings.last_ATIS_recorded == None:
			info_letter = 'A'
		else:
			info_letter = chr((ord(settings.last_ATIS_recorded) - ord('A') + 1) % 26 + ord('A'))
		custom_appendix = replace_text_aliases(settings.ATIS_custom_appendix, selection, False)
		self.notepad_textEdit.setPlainText(env.suggestedATIS(info_letter, custom_appendix))
		self.infoLetter_edit.setText(info_letter)
		self.instance = InternalFgcomInstance(settings.reserved_fgcom_port, cmdopts, self)
		self.record_button.clicked.connect(self.startRecording)
		self.close_button.clicked.connect(self.closeMe)
		self.instance.started.connect(self.processHasStarted)
		self.instance.finished.connect(self.processHasStopped)
	
	def startRecording(self):
		self.status_infoLabel.setText('Starting FGCom instance...')
		self.instance.start()
		#print('Executed: %s %s' % (self.instance.program(), ' '.join(self.instance.arguments())))
	
	def processHasStopped(self):
		self.status_infoLabel.setText('Process has stopped.')
	
	def processHasStarted(self):
		self.recorded = True
		self.record_button.setEnabled(False)
		self.status_infoLabel.setText('Speak after beep...')
	
	def closeMe(self):
		if self.instance.state() == QProcess.Running:
			self.instance.kill()
		if self.recorded:
			settings.last_ATIS_recorded = self.infoLetter_edit.text().upper()
			self.accept()
		else:
			self.reject()
	






class RadioCentrePane(QWidget, Ui_radioCentrePane):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		if env.airport_data == None: # no ATIS in CTR mode
			self.ATISfreq_combo.setEnabled(False)
			self.recordATIS_button.setEnabled(False)
		else:
			self.ATISfreq_combo.addFrequencies([(f, d) for f, d, t in env.frequencies if t == 'recorded'])
		self.setEnabled(False) # while no FGCom-compatible session is running
		self.available_internal_ports = set()
		self.last_FGCom_external_host = 'localhost'
		addExternalFGCom_action = QAction('Add box for an external FGCom client', self)
		addExternalFGCom_action.triggered.connect(self.addRadioBox_externalFGCom)
		addBox_menu = QMenu()
		addBox_menu.addAction(addExternalFGCom_action)
		self.addBox_button.setMenu(addBox_menu)
		self.addBox_button.clicked.connect(self.addRadioBox_internalFGCom)
		self.recordATIS_button.clicked.connect(self.recordATIS)
		self.muteAllRadios_tickBox.toggled.connect(self.toggleMuteAll)
		signals.kbdPTT.connect(self.generalKeyboardPTT)
		signals.mainWindowClosing.connect(self.removeAllBoxes)
		signals.sessionStarted.connect(self.sessionHasStarted)
		signals.sessionEnded.connect(self.sessionHasEnded)
	
	def sessionHasStarted(self):
		if settings.session_manager.session_type != SessionType.SOLO:
			self.available_internal_ports = set(settings.radio_fgcom_ports)
			self.setEnabled(True)
	
	def sessionHasEnded(self):
		self.removeAllBoxes()
		self.setEnabled(False)
	
	def radio(self, index):
		return self.radios_table.cellWidget(index, 0)
	
	def addRadioBox_externalFGCom(self):
		host, ok = QInputDialog.getText(self, 'External FGCom radio', 'Client host:', text=self.last_FGCom_external_host)
		if not ok:
			return
		port, ok = QInputDialog.getInt(self, 'External FGCom radio', 'Client port:', value=16661, min=1, max=65535)
		if ok:
			if (host, port) in [self.radio(i).clientAddress() for i in range(self.radios_table.rowCount())] \
					or host == 'localhost' and (port in settings.radio_fgcom_ports or port == settings.reserved_fgcom_port):
				QMessageBox.critical(self, 'Radio box error', 'Used or reserved address.')
			else:
				self.last_FGCom_external_host = host
				self.addRadioBox(RadioBox(self, host, port))
	
	def addRadioBox_internalFGCom(self):
		try:
			port = self.available_internal_ports.pop()
		except KeyError:
			QMessageBox.critical(self, 'Radio box error', \
				'No more ports available for a new FGCom instance.\nConsider adding ports or use an external client.')
		else:
			self.addRadioBox(RadioBox(self, None, port))
		
	def addRadioBox(self, radiobox):
		index = self.radios_table.rowCount()
		radiobox.kbdPTT_checkBox.setChecked(index == 0)
		radiobox.removeBox_button.clicked.connect(lambda: self.removeRadioBox(address=radiobox.clientAddress()))
		self.radios_table.insertRow(index)
		self.radios_table.setCellWidget(index, 0, radiobox)
		self.radios_table.scrollToBottom()
		self.radios_table.resizeColumnToContents(0)
		self.radios_table.resizeRowToContents(index)
	
	def removeRadioBox(self, address=None, index=None):
		if index == None:
			index = next(i for i in range(self.radios_table.rowCount()) if self.radio(i).clientAddress() == address)
		else:
			address = self.radio(index).clientAddress()
		box = self.radio(index)
		port = address[1] if box.isInternal() else None
		box.getReadyForRemoval()
		self.radios_table.removeRow(index)
		if port != None:
			self.available_internal_ports.add(port)
	
	def generalKeyboardPTT(self, key_number, toggle): # only one key for now
		for i in range(self.radios_table.rowCount()):
			box = self.radio(i)
			if box.kbdPTT_checkBox.isChecked():
				box.PTT(toggle)
	
	def toggleMuteAll(self, toggle):
		settings.FGCom_radios_muted = toggle
		for i in range(self.radios_table.rowCount()):
			self.radio(i).setVolume()
		
	def performEchoTest(self):
		EchoTestDialog(self).exec()
		
	def recordATIS(self):
		RecordAtisDialog(self.ATISfreq_combo.getFrequency(), self).exec()
	
	def removeAllBoxes(self):
		while self.radios_table.rowCount() > 0: # recovers all ports 
			self.removeRadioBox(index=0)
	
