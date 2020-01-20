
from PyQt5.QtWidgets import QWidget, QMessageBox
from ui.instructions import Ui_instructionPanel

from data.util import some, pop_all
from data.fpl import FPL
from data.params import Heading
from data.instruction import Instruction
from data.strip import parsed_route_detail

from session.config import settings
from session.env import env
from session.manager import SessionType

from gui.misc import signals, selection
from gui.actions import send_instruction


# ---------- Constants ----------

# -------------------------------


class InstructionsPanel(QWidget, Ui_instructionPanel):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.taxiAvoidsRunways_tickBox.setChecked(settings.taxi_instructions_avoid_runways)
		self.dest_edit.setClearButtonEnabled(True)
		# Buttons and signals
		self.sayIntentions_OK_button.clicked.connect(self.sendInstruction_sayIntentions)
		if env.airport_data == None:
			self.depInstr_page.setEnabled(False)
			self.appInstr_page.setEnabled(False)
			self.instr_tabs.setCurrentIndex(2) # self.navInstr_page
		else:
			self.setupRwyLists()
			signals.runwayUseChanged.connect(self.setupRwyLists)
			signals.localSettingsChanged.connect(self.setupRwyLists) # in case a RWY param changed
			signals.selectionChanged.connect(self.setupRwyLists)
			# Taxi & DEP tab buttons
			self.taxiAvoidsRunways_tickBox.toggled.connect(self.setTaxiAvoidsRunways)
			self.reportReady_OK_button.clicked.connect(self.sendInstruction_expectDepartureRunway)
			self.holdPosition_OK_button.clicked.connect(self.sendInstruction_holdPosition)
			self.lineUp_OK_button.clicked.connect(self.sendInstruction_lineUp)
			self.takeOff_OK_button.clicked.connect(self.sendInstruction_takeOff)
			# Arrival buttons
			self.interceptLOC_OK_button.clicked.connect(self.sendInstruction_interceptLocaliser)
			self.clearedAPP_OK_button.clicked.connect(self.sendInstruction_clearedApproach)
			self.expectArrRWY_OK_button.clicked.connect(self.sendInstruction_expectArrivalRunway)
			self.clearedToLand_OK_button.clicked.connect(self.sendInstruction_clearToLand)
			self.cancelApproach_OK_button.clicked.connect(self.sendInstruction_cancelApproach)
		# Nav buttons
		self.DCT_OK_button.clicked.connect(self.sendInstruction_DCT)
		self.hold_OK_button.clicked.connect(self.sendInstruction_hold)
		self.interceptNav_OK_button.clicked.connect(self.sendInstruction_interceptNav)
		self.speedYourDiscretion_OK_button.clicked.connect(self.sendInstruction_speedYourDiscretion)
		self.followRoute_OK_button.clicked.connect(self.sendInstruction_followRoute)
		# Other signals
		signals.selectionChanged.connect(self.updateDestOnNewSelection)
		signals.navpointClick.connect(lambda p: self.navpoint_edit.setText(p.code))
		signals.sessionStarted.connect(self.sessionHasStarted)
		signals.sessionEnded.connect(self.sessionHasEnded)
	
	def sessionHasStarted(self):
		if settings.session_manager.session_type == SessionType.TEACHER:
			self.dest_edit.setText('selection')
			self.dest_edit.setEnabled(False)
	
	def sessionHasEnded(self):
		self.dest_edit.setEnabled(True)
		self.dest_edit.clear()
	
	def updateDestOnNewSelection(self):
		if settings.session_manager.session_type != SessionType.TEACHER:
			self.dest_edit.setText(some(selection.selectedCallsign(), ''))
	
	def setupRwyLists(self):
		if env.airport_data != None:
			dep_rwys = [rwy for rwy in env.airport_data.allRunways() if rwy.use_for_departures]
			arr_rwys = [rwy for rwy in env.airport_data.allRunways() if rwy.use_for_arrivals]
			if selection.strip != None:
				acft_type = selection.strip.lookup(FPL.ACFT_TYPE, fpl=True)
				if acft_type != None:
					pop_all(dep_rwys, lambda rwy: not rwy.acceptsAcftType(acft_type))
					pop_all(arr_rwys, lambda rwy: not rwy.acceptsAcftType(acft_type))
			dep_lst = sorted([rwy.name for rwy in dep_rwys] if dep_rwys != [] else env.airport_data.runwayNames())
			arr_lst = sorted([rwy.name for rwy in arr_rwys] if arr_rwys != [] else env.airport_data.runwayNames())
			self.reportReadyRWY_select.clear()
			self.expectArrRWY_select.clear()
			self.reportReadyRWY_select.addItems(dep_lst)
			self.expectArrRWY_select.addItems(arr_lst)
	
	def setTaxiAvoidsRunways(self, b):
		settings.taxi_instructions_avoid_runways = b
	
	
	# SENDING INSTRUCTION TO CORRECT CALLSIGN
	
	def sendInstruction(self, instr): # FUTURE[CPDLC] when all/most panel instr's can be encoded: option to send through CPDLC
		send_instruction(self.dest_edit.text(), instr, False) # NOTE: callsign ignored if teaching
	
	# BUTTON CLICKS
	
	def sendInstruction_sayIntentions(self):
		self.sendInstruction(Instruction(Instruction.SAY_INTENTIONS))
	
	
	def sendInstruction_expectDepartureRunway(self):
		self.sendInstruction(Instruction(Instruction.EXPECT_RWY, arg=self.reportReadyRWY_select.currentText()))
	
	def sendInstruction_holdPosition(self):
		self.sendInstruction(Instruction(Instruction.HOLD_POSITION))
	
	
	def sendInstruction_lineUp(self):
		self.sendInstruction(Instruction(Instruction.LINE_UP))
	
	def sendInstruction_takeOff(self):
		self.sendInstruction(Instruction(Instruction.CLEARED_TKOF))
	
	
	def sendInstruction_expectArrivalRunway(self):
		self.sendInstruction(Instruction(Instruction.EXPECT_RWY, arg=self.expectArrRWY_select.currentText()))
	
	def sendInstruction_interceptLocaliser(self):
		self.sendInstruction(Instruction(Instruction.INTERCEPT_LOC))
	
	def sendInstruction_clearedApproach(self):
		self.sendInstruction(Instruction(Instruction.CLEARED_APP))
	
	def sendInstruction_clearToLand(self):
		self.sendInstruction(Instruction(Instruction.CLEARED_TO_LAND))
	
	def sendInstruction_cancelApproach(self):
		self.sendInstruction(Instruction(Instruction.CANCEL_APP))
	
	
	def sendInstruction_DCT(self):
		self.sendInstruction(Instruction(Instruction.VECTOR_DCT, arg=self.navpoint_edit.text()))
	
	def sendInstruction_hold(self):
		right_turns = self.hold_turn_select.currentText() == 'right'
		self.sendInstruction(Instruction(Instruction.HOLD, arg=(self.navpoint_edit.text(), right_turns)))
	
	def sendInstruction_interceptNav(self):
		heading = Heading(self.intercept_heading_edit.value(), False)
		self.sendInstruction(Instruction(Instruction.INTERCEPT_NAV, arg=(self.navpoint_edit.text(), heading)))
	
	def sendInstruction_speedYourDiscretion(self):
		self.sendInstruction(Instruction(Instruction.CANCEL_VECTOR_SPD))
	
	def sendInstruction_followRoute(self):
		strip = selection.strip
		if strip == None:
			QMessageBox.critical(self, 'Instruction error', 'No strip selected.')
		else:
			route = strip.lookup(parsed_route_detail)
			if route == None:
				QMessageBox.critical(self, 'Instruction error', 'No valid route on selected strip.')
			else:
				instr = Instruction(Instruction.FOLLOW_ROUTE, arg=route.dup())
				self.sendInstruction(instr)
