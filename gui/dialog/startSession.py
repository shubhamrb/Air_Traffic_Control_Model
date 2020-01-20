from PyQt5.QtWidgets import QDialog, QMessageBox

from ui.startFlightGearMPdialog import Ui_startFlightGearMPdialog
from ui.startSoloDialog_AD import Ui_startSoloDialog_AD
from ui.startStudentSessionDialog import Ui_startStudentSessionDialog

from data.util import some, INET_addr_str
from session.config import settings
from session.env import env
from session.flightGearMP import irc_available


# ---------- Constants ----------

# -------------------------------



class StartFlightGearMPdialog(QDialog, Ui_startFlightGearMPdialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.ircTextChat_tickBox.setEnabled(irc_available)
		self.buttonBox.accepted.connect(self.doOK)
		self.buttonBox.rejected.connect(self.reject)
	
	def showEvent(self, event):
		self.fgmsServer_info.setText(INET_addr_str(settings.FGMS_server_name, settings.FGMS_server_port))
		self.callsign_edit.setText(settings.location_code + 'obs') # should contain no whitespace, cf. use with IRC
		self.clientPort_edit.setValue(settings.FGMS_client_port)
		self.ircTextChat_tickBox.setChecked(irc_available and settings.MP_IRC_enabled)
		self.orsx_tickBox.setChecked(settings.MP_ORSX_enabled)
		self.callsign_edit.setFocus()
	
	def doOK(self):
		if self.callsign_edit.text() == '' or ' ' in self.callsign_edit.text():
			QMessageBox.critical(self, 'MP start error', 'Callsign required; no spaces allowed.')
		elif settings.MP_social_name == '':
			QMessageBox.critical(self, 'MP start error', 'No social name set for MP sessions; please edit system settings.')
		elif self.ircTextChat_tickBox.isChecked() and (settings.MP_IRC_server_name == '' or settings.MP_IRC_channel == ''):
			QMessageBox.critical(self, 'MP start error', 'IRC server and channel required; please edit system settings.')
		elif self.orsx_tickBox.isChecked() and settings.ORSX_server_name == '':
			QMessageBox.critical(self, 'MP start error', 'OpenRadar server address missing in the system settings.')
		else: # all OK; update settings and accept dialog
			settings.FGMS_client_port = self.clientPort_edit.value()
			settings.MP_IRC_enabled = self.ircTextChat_tickBox.isChecked()
			settings.MP_ORSX_enabled = self.orsx_tickBox.isChecked()
			self.accept()
	
	def chosenCallsign(self):
		return self.callsign_edit.text()







class StartSoloDialog_AD(QDialog, Ui_startSoloDialog_AD):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.GND_enabled = env.airport_data != None and len(env.airport_data.ground_net.taxiways()) > 0 \
				and len(env.airport_data.ground_net.parkingPositions()) > 0
		if self.GND_enabled:
			self.GND_tickBox.toggled.connect(self.updateOKbutton)
		else:
			self.GND_tickBox.setEnabled(False)
			self.GND_tickBox.setToolTip('Missing parking positions or taxi routes.')
		self.TWR_tickBox.toggled.connect(self.updateOKbutton)
		self.APP_tickBox.toggled.connect(self.updateOKbutton)
		self.DEP_tickBox.toggled.connect(self.updateOKbutton)
		self.updateOKbutton()
		self.OK_button.clicked.connect(self.doOK)
		self.cancel_button.clicked.connect(self.reject)
	
	def updateOKbutton(self):
		gnd, twr, app, dep = (box.isChecked() for box in [self.GND_tickBox, self.TWR_tickBox, self.APP_tickBox, self.DEP_tickBox])
		self.OK_button.setEnabled((gnd or twr or app or dep) and (not gnd or twr or not app and not dep))
	
	def doOK(self):
		settings.solo_role_GND = self.GND_tickBox.isChecked()
		settings.solo_role_TWR = self.TWR_tickBox.isChecked()
		settings.solo_role_APP = self.APP_tickBox.isChecked()
		settings.solo_role_DEP = self.DEP_tickBox.isChecked()
		self.accept()
	
	def chosenInitialTrafficCount(self):
		return self.initTrafficCount_edit.value()






class StartStudentSessionDialog(QDialog, Ui_startStudentSessionDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.teachingServiceHost_edit.setText(settings.teaching_service_host)
		self.teachingServicePort_edit.setValue(settings.teaching_service_port)
		self.updateOKbutton()
		self.teachingServiceHost_edit.textChanged.connect(self.updateOKbutton)
		self.accepted.connect(self.updateSettings)
	
	def updateOKbutton(self):
		self.OK_button.setEnabled(self.teachingServiceHost_edit.text() != '')
	
	def updateSettings(self):
		settings.teaching_service_host = self.teachingServiceHost_edit.text()
		settings.teaching_service_port = self.teachingServicePort_edit.value()




