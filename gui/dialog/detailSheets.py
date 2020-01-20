
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import QDateTime
from PyQt5.QtGui import QIcon
from ui.fplDetailsDialog import Ui_fplDetailsDialog
from ui.stripDetailsDialog import Ui_stripDetailsDialog

from datetime import timedelta, timezone

from session.config import settings
from session.env import env

from data.util import some
from data.db import wake_turb_cat
from data.fpl import FPL, FplError
from data.route import Route
from data.utc import now, datestr, timestr
from data.params import Heading, StdPressureAlt, Speed
from data.strip import rack_detail, assigned_SQ_detail, \
		assigned_heading_detail, assigned_speed_detail, assigned_altitude_detail

from gui.misc import signals, IconFile
from gui.dialog.miscDialogs import yesNo_question
from gui.dialog.routeDialog import RouteDialog
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

unracked_strip_str = '(unracked)'
link_new_FPL_str = 'New flight plan (opens editor)'

# -------------------------------



def strip_sheet_FPL_match(callsign_filter, fpl):
	return callsign_filter.upper() in some(fpl[FPL.CALLSIGN], '').upper() \
			and env.linkedStrip(fpl) == None and fpl.flightIsInTimeWindow(timedelta(hours=12))








class SharedDetailSheet:
	'''
	WARNING! Methods to define in subclasses:
	- get_detail (reads from strip or FPL)
	- set_detail (writes to strip or FPL)
	- resetData (should call this resetData after doing its additional work)
	- saveChangesAndClose (call this shared saveChangesAndClose)
	'''
	def __init__(self):
		self.route_edit.viewRoute_signal.connect(self.viewRoute)
		self.depAirportPicker_widget.recognised.connect(self.route_edit.setDEP)
		self.arrAirportPicker_widget.recognised.connect(self.route_edit.setARR)
		self.depAirportPicker_widget.unrecognised.connect(self.route_edit.resetDEP)
		self.arrAirportPicker_widget.unrecognised.connect(self.route_edit.resetARR)
		self.save_button.clicked.connect(self.saveChangesAndClose)
		self.resetData()
		self.aircraftType_edit.editTextChanged.connect(self.autoFillWTCfromType)
		self.autoFillWTC_button.toggled.connect(self.autoFillWTCtoggled)
		# FUTURE[tabOrder]: remove tab order corrections below? current Qt focus behaviour is currently bad wthout them
		self.setTabOrder(self.depAirportPicker_widget.focusProxy(), self.arrAirportPicker_widget)
		self.setTabOrder(self.arrAirportPicker_widget.focusProxy(), self.route_edit)
		self.setTabOrder(self.route_edit.focusProxy(), self.cruiseAlt_edit)
	
	def autoFillWTCfromType(self, dez):
		if self.autoFillWTC_button.isChecked():
			self.wakeTurbCat_select.setCurrentText(some(wake_turb_cat(dez), ''))
	
	def autoFillWTCtoggled(self, toggle):
		if toggle:
			self.autoFillWTCfromType(self.aircraftType_edit.currentText())
	
	def viewRoute(self):
		tas = Speed(self.TAS_edit.value()) if self.TAS_enable.isChecked() else None
		route_to_view = Route(self.route_edit.data_DEP, self.route_edit.data_ARR, self.route_edit.getRouteText())
		RouteDialog(route_to_view, speedHint=tas, acftHint=self.aircraftType_edit.getAircraftType(), parent=self).exec()
	
	def resetData(self):
		# FPL.CALLSIGN
		self.callsign_edit.setText(some(self.get_detail(FPL.CALLSIGN), ''))
		#	FLIGHT_RULES
		self.flightRules_select.setCurrentText(some(self.get_detail(FPL.FLIGHT_RULES), ''))
		# FPL.ACFT_TYPE
		self.aircraftType_edit.setCurrentText(some(self.get_detail(FPL.ACFT_TYPE), ''))
		# FPL.WTC
		self.wakeTurbCat_select.setCurrentText(some(self.get_detail(FPL.WTC), ''))
		# FPL.ICAO_DEP
		self.depAirportPicker_widget.setEditText(some(self.get_detail(FPL.ICAO_DEP), ''))
		# FPL.ICAO_ARR
		self.arrAirportPicker_widget.setEditText(some(self.get_detail(FPL.ICAO_ARR), ''))
		#	ROUTE
		self.route_edit.setRouteText(some(self.get_detail(FPL.ROUTE), ''))
		#	CRUISE_ALT
		self.cruiseAlt_edit.setText(some(self.get_detail(FPL.CRUISE_ALT), ''))
		#	TAS
		tas = self.get_detail(FPL.TAS)
		self.TAS_enable.setChecked(tas != None)
		if tas != None:
			self.TAS_edit.setValue(tas.kt)
		#	COMMENTS
		self.comments_edit.setPlainText(some(self.get_detail(FPL.COMMENTS), ''))
		self.callsign_edit.setFocus()
		
	def saveChangesAndClose(self):
		# FPL.CALLSIGN
		self.set_detail(FPL.CALLSIGN, self.callsign_edit.text().upper())
		# FPL.FLIGHT_RULES
		self.set_detail(FPL.FLIGHT_RULES, self.flightRules_select.currentText())
		# FPL.ACFT_TYPE
		self.set_detail(FPL.ACFT_TYPE, self.aircraftType_edit.getAircraftType())
		# FPL.WTC
		self.set_detail(FPL.WTC, self.wakeTurbCat_select.currentText())
		# FPL.ICAO_DEP
		self.set_detail(FPL.ICAO_DEP, self.depAirportPicker_widget.currentText())
		# FPL.ICAO_ARR
		self.set_detail(FPL.ICAO_ARR, self.arrAirportPicker_widget.currentText())
		# FPL.ROUTE
		self.set_detail(FPL.ROUTE, self.route_edit.getRouteText())
		# FPL.CRUISE_ALT
		self.set_detail(FPL.CRUISE_ALT, self.cruiseAlt_edit.text())
		# FPL.TAS
		self.set_detail(FPL.TAS, (Speed(self.TAS_edit.value()) if self.TAS_enable.isChecked() else None))
		# FPL.COMMENTS
		self.set_detail(FPL.COMMENTS, self.comments_edit.toPlainText())













# =========== STRIP =========== #

class StripDetailSheetDialog(QDialog, Ui_stripDetailsDialog, SharedDetailSheet):
	def __init__(self, gui, strip):
		QDialog.__init__(self, gui)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.setWindowIcon(QIcon(IconFile.pixmap_strip))
		self.linkFPL_reset_button.setIcon(QIcon(IconFile.button_clear))
		self.strip = strip
		self.FPL_link_on_save = None # None to link a new FPL
		self.FPL_matches = [] # Flight plans matching the last callsign edit
		if self.strip.lookup(rack_detail) == None: # unracked strip
			self.rack_select.addItem(unracked_strip_str)
			self.rack_select.setEnabled(False)
		else:
			self.rack_select.addItems(env.strips.rackNames())
		ro_tod = strip.lookup(FPL.TIME_OF_DEP)
		ro_eet = strip.lookup(FPL.EET)
		ro_altAD = strip.lookup(FPL.ICAO_ALT)
		ro_souls = strip.lookup(FPL.SOULS)
		self.depAirportPicker_widget.recognised.connect(lambda ad: self.depAirportName_info.setText(ad.long_name))
		self.arrAirportPicker_widget.recognised.connect(lambda ad: self.arrAirportName_info.setText(ad.long_name))
		self.depAirportPicker_widget.unrecognised.connect(self.depAirportName_info.clear)
		self.arrAirportPicker_widget.unrecognised.connect(self.arrAirportName_info.clear)
		self.cruiseAlt_edit.textChanged.connect(self.updateCruiseButton)
		self.assignCruiseAlt_button.clicked.connect(self.assignCruiseLevel)
		linkedFPL = self.strip.linkedFPL()
		if linkedFPL == None:
			self.fplLink_stackedWidget.setCurrentWidget(self.noFplLink_page)
			self.updateFplToLinkInfo()
			self.matchingFPLs_button.clicked.connect(self.matchingFPLsButtonClicked)
			self.callsign_edit.textChanged.connect(self.updateMatchingFPLs)
			self.linkFPL_tickBox.toggled.connect(self.updateFplToLinkInfo)
			self.linkFPL_reset_button.clicked.connect(self.fplToLinkReset)
		else: # a flight plan is already linked
			self.matchingFPLs_button.setVisible(False)
			self.fplLink_stackedWidget.setCurrentWidget(self.gotFplLink_page)
			self.linkedFPL_info.setText(linkedFPL.shortDescr())
		SharedDetailSheet.__init__(self)
		if self.strip.linkedFPL() == None:
			self.updateMatchingFPLs(self.callsign_edit.text())
	
	def matchingFPLsButtonClicked(self):
		if len(self.FPL_matches) == 1:
			if yesNo_question(self, 'Single matching FPL', self.FPL_matches[0].shortDescr(), \
					'Do you want to link this flight plan when saving the strip?'):
				self.linkFPL_tickBox.setChecked(True)
				self.FPL_link_on_save = self.FPL_matches[0]
				self.updateFplToLinkInfo()
		else:
			msg = '%d flight plans today matching callsign filter:\n' % len(self.FPL_matches)
			msg += '\n'.join('  %s' % fpl.shortDescr() for fpl in self.FPL_matches)
			QMessageBox.information(self, 'Matching FPLs', msg)
	
	def fplToLinkReset(self):
		self.FPL_link_on_save = None
		self.updateFplToLinkInfo()
	
	def updateFplToLinkInfo(self):
		if self.linkFPL_tickBox.isChecked():
			if self.FPL_link_on_save == None:
				self.linkFPL_info.setText(link_new_FPL_str)
			else:
				self.linkFPL_info.setText(self.FPL_link_on_save.shortDescr())
			self.linkFPL_reset_button.setEnabled(self.FPL_link_on_save != None)
		else:
			self.linkFPL_info.setText('none')
			self.linkFPL_reset_button.setEnabled(False)
	
	def updateMatchingFPLs(self, cs):
		self.FPL_matches = env.FPLs.findAll(lambda fpl: strip_sheet_FPL_match(cs, fpl))
		self.matchingFPLs_button.setVisible(len(self.FPL_matches) > 0)
		self.matchingFPLs_button.setText('(%d)' % len(self.FPL_matches))
	
	def updateCruiseButton(self, cruise_alt_text):
		self.assignCruiseAlt_button.setEnabled(cruise_alt_text != '')
	
	def assignCruiseLevel(self):
		self.assignAltitude.setChecked(True)
		self.assignedAltitude_edit.setText(self.cruiseAlt_edit.text())
	
	def get_detail(self, detail):
		return self.strip.lookup(detail)
	
	def set_detail(self, detail, new_val):
		self.strip.writeDetail(detail, new_val)
	
	def selectedRack(self):
		return None if self.strip.lookup(rack_detail) == None else self.rack_select.currentText()
	
	def resetData(self):
		## Rack
		self.rack_select.setCurrentText(some(self.strip.lookup(rack_detail), unracked_strip_str))
		## Assigned stuff
		# Squawk code
		assSQ = self.strip.lookup(assigned_SQ_detail)
		self.assignSquawkCode.setChecked(assSQ != None)
		if assSQ != None:
			self.xpdrCode_select.setSQ(assSQ)
		# Heading
		assHdg = self.strip.lookup(assigned_heading_detail)
		self.assignHeading.setChecked(assHdg != None)
		if assHdg != None:
			self.assignedHeading_edit.setValue(int(assHdg.read()))
		# Altitude/FL
		assAlt = self.strip.lookup(assigned_altitude_detail)
		self.assignAltitude.setChecked(assAlt != None)
		if assAlt != None:
			self.assignedAltitude_edit.setText(assAlt)
		# Speed
		assSpd = self.strip.lookup(assigned_speed_detail)
		self.assignSpeed.setChecked(assSpd != None)
		if assSpd != None:
			self.assignedSpeed_edit.setValue(assSpd.kt)
		## Links and conflicts:
		acft = self.strip.linkedAircraft()
		if acft == None:
			self.xpdrConflicts_info.setText('no link')
		else:
			clst = self.strip.transponderConflictList()
			self.xpdrConflicts_info.setText('no conflicts' if clst == [] else 'conflicts ' + ', '.join(clst))
		fpl = self.strip.linkedFPL()
		if fpl == None:
			self.fplConflicts_info.setText('no link')
		else:
			clst = self.strip.FPLconflictList()
			self.fplConflicts_info.setText('no conflicts' if clst == [] else 'conflicts ' + ', '.join(clst))
		## FPL stuff
		SharedDetailSheet.resetData(self)
	
	def saveChangesAndClose(self):
		SharedDetailSheet.saveChangesAndClose(self)
		## Assigned stuff
		# Squawk code
		if self.assignSquawkCode.isChecked():
			self.set_detail(assigned_SQ_detail, self.xpdrCode_select.getSQ())
		else:
			self.set_detail(assigned_SQ_detail, None)
		# Heading
		if self.assignHeading.isChecked():
			self.set_detail(assigned_heading_detail, Heading(self.assignedHeading_edit.value(), False))
		else:
			self.set_detail(assigned_heading_detail, None)
		# Altitude/FL
		if self.assignAltitude.isChecked():
			reading = self.assignedAltitude_edit.text()
			try: # try reformating
				self.set_detail(assigned_altitude_detail, StdPressureAlt.reformatReading(reading))
			except ValueError:
				self.set_detail(assigned_altitude_detail, reading)
		else:
			self.set_detail(assigned_altitude_detail, None)
		# Speed
		if self.assignSpeed.isChecked():
			self.set_detail(assigned_speed_detail, Speed(self.assignedSpeed_edit.value()))
		else:
			self.set_detail(assigned_speed_detail, None)
		# DONE with details
		if self.strip.linkedFPL() == None:
			if self.linkFPL_tickBox.isChecked():
				if self.FPL_link_on_save == None:
					signals.newLinkedFPLrequest.emit(self.strip)
				else:
					self.strip.linkFPL(self.FPL_link_on_save)
		else: # a flight plan is already linked
			if self.pushToFPL_tickBox.isChecked():
				self.strip.pushToFPL()
		self.accept()
		# WARNING: deal with self.rack_select change after dialog accept (use selectedRack method)



















# =========== FPL =========== #

class FPLdetailSheetDialog(QDialog, Ui_fplDetailsDialog, SharedDetailSheet):
	def __init__(self, gui, fpl):
		QDialog.__init__(self, gui)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.setWindowIcon(QIcon(IconFile.panel_FPLs))
		self.fpl = fpl
		self.updateOnlineStatusBox()
		self.stripLinked_info.setText('yes' if env.linkedStrip(self.fpl) != None else 'no')
		SharedDetailSheet.__init__(self)
		self.viewOnlineComments_button.clicked.connect(self.viewOnlineComments)
		self.openFPL_button.clicked.connect(lambda: self.changeFplOnlineStatus(FPL.OPEN))
		self.closeFPL_button.clicked.connect(lambda: self.changeFplOnlineStatus(FPL.CLOSED))
		# FUTURE[tabOrder]: remove tab order corrections below? current Qt focus behaviour is currently bad wthout them
		self.setTabOrder(self.cruiseAlt_edit, self.altAirportPicker_widget)
		self.setTabOrder(self.altAirportPicker_widget.focusProxy(), self.flightRules_select)
	
	def updateOnlineStatusBox(self):
		if self.fpl.existsOnline():
			online_status = self.fpl.status()
			self.openFPL_button.setEnabled(online_status == FPL.FILED)
			self.closeFPL_button.setEnabled(online_status == FPL.OPEN)
			status_txt = {FPL.FILED: 'filed', FPL.OPEN: 'open', FPL.CLOSED: 'closed'}.get(online_status, 'unknown')
			changes_txt = ', '.join(FPL.detailStrNames[d] for d in self.fpl.modified_details) if self.fpl.needsUpload() else 'none'
		else: # FPL is not "online"
			self.openFPL_button.setEnabled(False)
			self.closeFPL_button.setEnabled(False)
			status_txt = 'not online'
			changes_txt = '--'
		self.onlineStatus_infoLabel.setText(status_txt)
		self.syncStatus_infoLabel.setText(changes_txt)
		self.publishOnlineOnSave_tickBox.setEnabled(settings.session_manager.has_online_FPLs and settings.session_manager.isRunning())
	
	def get_detail(self, detail):
		return self.fpl[detail]
	
	def set_detail(self, detail, new_val):
		self.fpl[detail] = new_val
	
	def viewOnlineComments(self):
		QMessageBox.information(self, 'Online FPL comments', '\n'.join(self.fpl.onlineComments()))
	
	def changeFplOnlineStatus(self, new_status):
		t = now()
		if new_status == FPL.OPEN:
			text = 'Do you want also to update departure time with the current date & time below?\n%s, %s' % (datestr(t), timestr(t))
			text += '\n\nWARNING: Answering "yes" or "no" will open the flight plan online.'
			button = QMessageBox.question(self, 'Open FPL', text, buttons=(QMessageBox.Cancel | QMessageBox.No | QMessageBox.Yes))
			if button == QMessageBox.Yes:
				self.depTime_edit.setDateTime(QDateTime(t.year, t.month, t.day, t.hour, t.minute))
			ok = button != QMessageBox.Cancel
		elif new_status == FPL.CLOSED:
			ok = yesNo_question(self, 'Close FPL', 'Time is %s.' % timestr(t), 'This will close the flight plan online. OK?')
		if ok:
			try:
				settings.session_manager.changeFplStatus(self.fpl, new_status)
			except FplError as err:
				QMessageBox.critical(self, 'FPL open/close error', str(err))
			self.updateOnlineStatusBox()
	
	def resetData(self):
		# FPL.TIME_OF_DEP
		dep = self.fpl[FPL.TIME_OF_DEP]
		self.depTime_enable.setChecked(dep != None)
		if dep == None:
			dep = now()
		self.depTime_edit.setDateTime(QDateTime(dep.year, dep.month, dep.day, dep.hour, dep.minute))
		# FPL.EET
		eet = self.fpl[FPL.EET]
		self.EET_enable.setChecked(eet != None)
		if eet != None:
			minutes = int(eet.total_seconds() / 60 + .5)
			self.EETh_edit.setValue(minutes // 60)
			self.EETmin_edit.setValue(minutes % 60)
		#	ICAO_ALT
		self.altAirportPicker_widget.setEditText(some(self.fpl[FPL.ICAO_ALT], ''))
		#	SOULS
		souls = self.fpl[FPL.SOULS]
		self.soulsOnBoard_enable.setChecked(souls != None)
		if souls != None:
			self.soulsOnBoard_edit.setValue(souls)
		# ONLINE COMMENTS
		self.viewOnlineComments_button.setEnabled(self.fpl.onlineComments() != [])
		SharedDetailSheet.resetData(self)
	
	def saveChangesAndClose(self):
		SharedDetailSheet.saveChangesAndClose(self)
		# FPL.TIME_OF_DEP
		if self.depTime_enable.isChecked():
			self.set_detail(FPL.TIME_OF_DEP, self.depTime_edit.dateTime().toPyDateTime().replace(tzinfo=timezone.utc))
		else:
			self.set_detail(FPL.TIME_OF_DEP, None)
		# FPL.EET
		if self.EET_enable.isChecked():
			self.set_detail(FPL.EET, timedelta(hours=self.EETh_edit.value(), minutes=self.EETmin_edit.value()))
		else:
			self.set_detail(FPL.EET, None)
		# FPL.ICAO_ALT
		self.set_detail(FPL.ICAO_ALT, self.altAirportPicker_widget.currentText())
		# FPL.SOULS
		self.set_detail(FPL.SOULS, (self.soulsOnBoard_edit.value() if self.soulsOnBoard_enable.isChecked() else None))
		# Done details!
		if self.publishOnlineOnSave_tickBox.isChecked():
			try:
				settings.session_manager.pushFplOnline(self.fpl)
			except FplError as err:
				QMessageBox.critical(self, 'FPL upload error', str(err))
				return
		self.accept()

