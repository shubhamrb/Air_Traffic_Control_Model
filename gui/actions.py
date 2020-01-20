from PyQt5.QtWidgets import QMessageBox, QInputDialog

from session.config import settings
from session.env import env
from session.manager import SessionType, CpdlcAuthorityTransferFailed

from models.liveStrips import default_rack_name

from data.util import some
from data.utc import now, rel_datetime_str
from data.fpl import FPL, FplError
from data.comms import CpdlcMessage
from data.strip import Strip, recycled_detail, auto_printed_detail, shelved_detail, \
		runway_box_detail, rack_detail, received_from_detail

from gui.misc import signals, selection
from gui.dialog.miscDialogs import yesNo_question
from gui.dialog.detailSheets import StripDetailSheetDialog


# ---------- Constants ----------

# -------------------------------


#############################

##    MANIPULATE STRIPS    ##

#############################
	

def new_strip_dialog(parent_widget, rack, linkToSelection=False):
	'''
	Returns the created strip if operation not aborted
	'''
	new_strip = Strip()
	new_strip.writeDetail(rack_detail, rack)
	if linkToSelection:
		new_strip.linkAircraft(selection.acft)
		if settings.strip_autofill_on_ACFT_link:
			new_strip.fillFromXPDR()
		new_strip.linkFPL(selection.fpl)
	dialog = StripDetailSheetDialog(parent_widget, new_strip)
	dialog.exec()
	if dialog.result() > 0: # not rejected
		new_strip.writeDetail(rack_detail, dialog.selectedRack())
		env.strips.addStrip(new_strip)
		selection.selectStrip(new_strip)
		return new_strip
	else:
		return None


def discard_strip(parent_widget, strip, shelve):
	'''
	Returns the discarded strip if operation not aborted.
	Argument "shelve" is True to shelve; False to delete.
	'''
	if strip == None:
		return
	acft = strip.linkedAircraft()
	fpl = strip.linkedFPL()
	if shelve: # shelving strip
		if fpl == None or strip.FPLconflictList() != []:
			if settings.confirm_lossy_strip_releases and not yesNo_question(parent_widget, 'Lossy shelving', \
					'Strip has conflicts or no linked flight plan.', 'Release contact losing strip details?'):
				signals.stripEditRequest.emit(strip)
				return # abort shelving
		elif not fpl.existsOnline() or fpl.needsUpload():
			if settings.confirm_lossy_strip_releases and not yesNo_question(parent_widget, 'Lossy shelving', \
					'Linked FPL is not online or has local changes.', 'Release contact without pushing details online?'):
				signals.FPLeditRequest.emit(fpl)
				return # abort shelving
		if fpl != None and fpl.status() == FPL.OPEN: # no aborting here, but offer to close FPL if releasing at destination
			if env.airport_data != None and fpl[FPL.ICAO_ARR] == env.airport_data.navpoint.code:
				if yesNo_question(parent_widget, 'Shelving with open FPL', \
						'Linked FPL is open and arrival filed at location.', 'Would you like to close the flight plan?'):
					try:
						settings.session_manager.changeFplStatus(fpl, FPL.CLOSED)
					except FplError as err:
						QMessageBox.critical(parent_widget, 'FPL open/close error', str(err))
	else: # deleting strip (not shelving)
		if acft != None or fpl != None:
			if settings.confirm_linked_strip_deletions and not yesNo_question(parent_widget, 'Delete strip', 'Strip is linked.', 'Delete?'):
				return # abort deletion
	strip.linkAircraft(None)
	strip.linkFPL(None)
	env.strips.removeStrip(strip)
	strip.writeDetail(shelved_detail, shelve)
	env.discarded_strips.addStrip(strip)
	if strip is selection.strip:
		selection.deselect()
	return strip




def edit_strip(parent_widget, strip):
	old_rack = strip.lookup(rack_detail) # may be None
	dialog = StripDetailSheetDialog(parent_widget, strip)
	dialog.exec()
	new_rack = dialog.selectedRack()
	if dialog.result() > 0 and new_rack != old_rack: # not rejected and rack changed
		env.strips.repositionStrip(strip, new_rack)
	signals.stripInfoChanged.emit()
	signals.selectionChanged.emit()





def pull_XPDR_details(parent_widget):
	if yesNo_question(parent_widget, 'Pull XPDR details', 'This will overwrite strip details.', 'Are you sure?'):
		selection.strip.fillFromXPDR(ovr=True)
	signals.stripInfoChanged.emit()

def pull_FPL_details(parent_widget):
	if yesNo_question(parent_widget, 'Pull FPL details', 'This will overwrite strip details.', 'Are you sure?'):
		selection.strip.fillFromFPL(ovr=True)
	signals.stripInfoChanged.emit()



def receive_strip(strip):
	rack = strip.lookup(rack_detail)
	if rack == None:
		recv_from = strip.lookup(received_from_detail)
		if recv_from != None:
			rack = settings.ATC_collecting_racks.get(recv_from, default_rack_name)
	if rack not in env.strips.rackNames():
		rack = default_rack_name
	strip.writeDetail(rack_detail, rack)
	env.strips.addStrip(strip)

def recover_strip(strip):
	env.discarded_strips.remove(strip)
	strip.writeDetail(recycled_detail, True)
	strip.writeDetail(shelved_detail, None)
	strip.writeDetail(runway_box_detail, None)
	strip.writeDetail(rack_detail, default_rack_name)
	env.strips.addStrip(strip)





##############################

##     INSTRUCTING ACFT     ##

##############################


def send_instruction(callsign, instr, consider_cpdlc):
	'''
	Teacher sessions: direct control of selected aircraft with given instr (callsign match bypass).
	Other sessions:
	 - perform manager-dependant instruction to callsign
	 - give a cpdlcSuggGui to suggest sending through data link instead, if callsign is connected
	CAUTION: Instruction.encodeToStr raises NotImplementedError with non-encoded instruction types.
	'''
	if settings.session_manager.session_type == SessionType.TEACHER:
		if selection.acft == None:
			QMessageBox.critical(settings.session_manager.gui, 'Traffic command error', 'No aircraft selected.')
		elif settings.teacher_ACFT_requesting_CPDLC_vectors == selection.acft.identifier:
			instr_str = instr.encodeToStr()
			settings.session_manager.sendCpdlcMsg(selection.acft.identifier, CpdlcMessage(True, CpdlcMessage.REQUEST, contents=instr_str))
			QMessageBox.information(settings.session_manager.gui, 'CPDLC request sent', 'Requested through data link: ' + instr_str)
		else:
			settings.session_manager.instructAircraftByCallsign(selection.acft.identifier, instr)
	elif consider_cpdlc and env.cpdlc.isConnected(callsign) and yesNo_question(settings.session_manager.gui, \
			'Send CPDLC instruction', instr.encodeToStr(), 'Send this instruction through data link to %s?' % callsign):
		settings.session_manager.sendCpdlcMsg(callsign, CpdlcMessage(True, CpdlcMessage.INSTR, contents=instr.encodeToStr()))
	else:
		settings.session_manager.instructAircraftByCallsign(callsign, instr)



def instruct_selected_with_vector(instr):
	send_instruction(some(selection.selectedCallsign(), ''), instr, settings.CPDLC_suggest_vector_instructions)


def instruct_selected_with_taxi(instr):
	send_instruction(some(selection.selectedCallsign(), ''), instr, False)


def transfer_selected_or_instruct(next_atc_callsign):
	'''
	CAUTION: Should not be called as teacher
	'''
	assert settings.session_manager.session_type != SessionType.TEACHER
	selected_callsign = selection.selectedCallsign()
	data_auth_transferred = False
	if settings.CPDLC_authority_transfers and selected_callsign != None and env.cpdlc.isConnected(selected_callsign):
		try:
			settings.session_manager.transferCpdlcAuthority(selected_callsign, next_atc_callsign)
			data_auth_transferred = True
		except CpdlcAuthorityTransferFailed:
			pass
	if data_auth_transferred:
		QMessageBox.information(settings.session_manager.gui, 'CPDLC transfer', \
				'Data authority transferred to %s' % next_atc_callsign)
	else: # Hand over through regular instruction, possibly through data link
		instr = env.ATCs.handoverInstructionTo(next_atc_callsign)
		send_instruction(some(selected_callsign, ''), instr, settings.CPDLC_suggest_handover_instructions)





##############################

##     STRIP AUTO-PRINT     ##

##############################

def auto_print_strip_reason(fpl):
	'''
	Returns reason to print if strip should be auto-printed from FPL; None otherwise
	'''
	if fpl.status() == FPL.CLOSED or fpl.strip_auto_printed \
	or settings.auto_print_strips_IFR_only and fpl[FPL.FLIGHT_RULES] != 'IFR' \
	or env.airport_data == None or env.linkedStrip(fpl) != None:
		return None
	present_time = now()
	ok_reason = None
	if settings.auto_print_strips_include_DEP: # check DEP time
		dep = fpl[FPL.TIME_OF_DEP]
		if dep != None and fpl[FPL.ICAO_DEP] == env.airport_data.navpoint.code: # we know: fpl.status() != FPL.CLOSED
			if dep - settings.auto_print_strips_anticipation <= present_time <= dep:
				ok_reason = 'departure due ' + rel_datetime_str(dep)
	if ok_reason == None and settings.auto_print_strips_include_ARR: # check ARR time
		eta = fpl.ETA()
		if eta != None and fpl[FPL.ICAO_ARR] == env.airport_data.navpoint.code and fpl.status() == FPL.OPEN:
			if eta - settings.auto_print_strips_anticipation <= present_time <= eta:
				ok_reason = 'arrival due ' + rel_datetime_str(eta)
	return ok_reason


def strip_auto_print_check():
	if settings.session_manager.isRunning():
		for fpl in env.FPLs.findAll():
			reason_to_print = auto_print_strip_reason(fpl)
			if reason_to_print != None:
				strip = Strip()
				strip.linkFPL(fpl)
				strip.writeDetail(rack_detail, some(settings.auto_print_collecting_rack, default_rack_name))
				strip.writeDetail(auto_printed_detail, True)
				fpl.strip_auto_printed = True
				env.strips.addStrip(strip)
				signals.stripAutoPrinted.emit(strip, reason_to_print)
				signals.selectionChanged.emit()






##############################

##     WHO-HAS REQUESTS     ##

##############################


def answer_who_has(callsign):
	ok = lambda s: s.callsign(acft=True).upper() == callsign.upper() and s.lookup(rack_detail) not in settings.private_racks
	try:
		env.strips.findStrip(ok) # ignore result
		return True
	except StopIteration:
		return False

