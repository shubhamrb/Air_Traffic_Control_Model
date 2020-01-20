
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from ui.createTrafficDialog import Ui_createTrafficDialog

from session.config import settings
from session.env import env
from session.manager import CallsignGenerationError

from data.util import some
from data.db import known_airline_codes, known_aircraft_types, cruise_speed
from data.params import StdPressureAlt, Speed

from ai.status import Status, SoloParams
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

max_spawn_THR_dist = .25 # NM
max_spawn_PKG_dist = .05 # NM
max_spawn_GND_dist = 1 # NM

# -------------------------------


class CreateTrafficDialog(QDialog, Ui_createTrafficDialog):
	last_known_acft_type_used = 'B772'
	last_strip_link = True
	last_start_frozen = False
	
	def __init__(self, spawn_coords, spawn_hdg, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.createCallsign_edit.setClearButtonEnabled(True)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.createAircraftType_edit.setAircraftFilter(lambda t: cruise_speed(t) != None)
		self.airline_codes = known_airline_codes()
		self.createAircraftType_edit.setEditText(CreateTrafficDialog.last_known_acft_type_used)
		self.startFrozen_tickBox.setChecked(CreateTrafficDialog.last_start_frozen)
		self.createStripLink_tickBox.setChecked(CreateTrafficDialog.last_strip_link)
		self.suggestCallsign()
		if env.airport_data == None:
			self.allow_taxi = False
			self.closest_PKG = None
			self.nearby_THRs = []
		else:
			self.allow_taxi = env.airport_data.ground_net.closestNode(spawn_coords, maxdist=max_spawn_GND_dist) != None
			self.closest_PKG = env.airport_data.ground_net.closestParkingPosition(spawn_coords, maxdist=max_spawn_PKG_dist)
			self.nearby_THRs = [r.name for r in env.airport_data.allRunways() if r.threshold().distanceTo(spawn_coords) <= max_spawn_THR_dist]
		self.closestParkingPosition_info.setText(some(self.closest_PKG, ''))
		self.depRWY_select.addItems(sorted(self.nearby_THRs))
		self.spawn_coords = spawn_coords
		self.spawn_hdg = spawn_hdg
		self.updateButtons()
		if self.allow_taxi:
			self.ground_status_radioButton.toggled.connect(self.toggleGroundStatus)
			self.ground_status_radioButton.setChecked(True)
			if self.closest_PKG != None:
				self.parked_tickBox.setChecked(True)
		else:
			self.ground_status_radioButton.setEnabled(False)
			self.toggleGroundStatus(False)
		self.depRWY_select.setEnabled(False)
		if self.nearby_THRs == []:
			self.ready_status_radioButton.setEnabled(False)
		elif self.closest_PKG == None:
			self.ready_status_radioButton.setChecked(True)
		self.accepted.connect(self.rememberOptions)
		self.createAircraftType_edit.editTextChanged.connect(self.updateButtons)
		self.createAircraftType_edit.editTextChanged.connect(self.suggestCallsign)
		self.createCallsign_edit.textChanged.connect(self.updateButtons)
	
	def toggleGroundStatus(self, toggle):
		self.parked_tickBox.setEnabled(toggle and self.closest_PKG != None)
		self.closestParkingPosition_info.setEnabled(toggle and self.closest_PKG != None)
	
	def suggestCallsign(self):
		t = self.createAircraftType_edit.getAircraftType()
		if t in known_aircraft_types():
			try:
				self.createCallsign_edit.setText(settings.session_manager.generateCallsign(t, self.airline_codes))
			except CallsignGenerationError:
				self.createCallsign_edit.setText('')
	
	def updateButtons(self):
		cs = self.createCallsign_edit.text()
		t = self.createAircraftType_edit.getAircraftType()
		ok = cs != ''
		ok &= all(cs != acft.identifier for acft in settings.session_manager.getAircraft())
		ok &= cs not in env.ATCs.knownATCs()
		ok &= t in known_aircraft_types() and cruise_speed(t) != None
		self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(ok)
	
	def acftCallsign(self):
		return self.createCallsign_edit.text()
	
	def acftType(self):
		return self.createAircraftType_edit.getAircraftType()
	
	def startFrozen(self):
		return self.startFrozen_tickBox.isChecked()
	
	def createStrip(self):
		return self.createStripLink_tickBox.isChecked()
	
	def acftInitParams(self):
		if self.ground_status_radioButton.isChecked():
			status = Status(Status.TAXIING)
		elif self.ready_status_radioButton.isChecked():
			status = Status(Status.READY, arg=self.depRWY_select.currentText())
		else: # airborne status radio button must be ticked
			status = Status(Status.AIRBORNE)
		pos = self.spawn_coords
		hdg = self.spawn_hdg
		if self.airborne_status_radioButton.isChecked():
			ias = cruise_speed(self.createAircraftType_edit.getAircraftType())
			alt = StdPressureAlt.fromFL(self.airborneFL_edit.value())
		else: # on ground
			ias = Speed(0)
			alt = env.groundStdPressureAlt(pos)
			if self.parked_tickBox.isChecked() and self.closest_PKG != None:
				pkinf = env.airport_data.ground_net.parkingPosInfo(self.closest_PKG)
				pos = pkinf[0]
				hdg = pkinf[1]
		return SoloParams(status, pos, alt, hdg, ias)
	
	def rememberOptions(self): # on dialog accept
		t = self.acftType()
		if t in known_aircraft_types(): # normally it is since we do not allow others for now
			CreateTrafficDialog.last_known_acft_type_used = t
		CreateTrafficDialog.last_strip_link = self.createStrip()
		CreateTrafficDialog.last_start_frozen = self.startFrozen()


