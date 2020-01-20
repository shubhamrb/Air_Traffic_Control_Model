
import re
from math import atan, degrees

from PyQt5.QtCore import Qt, QDateTime, QTime, QAbstractTableModel
from PyQt5.QtWidgets import QDialog, QMessageBox, QColorDialog, QLabel
from PyQt5.QtGui import QIcon

from ui.postLennySessionDialog import Ui_postLennySessionDialog
from ui.envInfoDialog import Ui_envInfoDialog
from ui.aboutDialog import Ui_aboutDialog
from ui.routeSpecsLostDialog import Ui_routeSpecsLostDialog
from ui.discardedStripsDialog import Ui_discardedStripsDialog
from ui.editRackDialog import Ui_editRackDialog

from session.config import settings, version_string
from session.env import env

from models.liveStrips import default_rack_name

from ext.xplane import surface_types
from ext.lenny64 import post_session, Lenny64Error

from data.util import some
from data.utc import now
from data.coords import m2NM
from data.strip import Strip, rack_detail, runway_box_detail, recycled_detail

from gui.misc import signals, IconFile
from gui.widgets.miscWidgets import RadioKeyEventFilter


# ---------- Constants ----------

version_string_placeholder = '##version##'

# -------------------------------


def yesNo_question(parent_window, title, text, question):
	return QMessageBox.question(parent_window, title, text + '\n' + question) == QMessageBox.Yes




class PostLennySessionDialog(QDialog, Ui_postLennySessionDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		t = now()
		qdt = QDateTime(t.year, t.month, t.day, t.hour, t.minute, timeSpec=Qt.UTC)
		self.beginTime_edit.setDateTime(qdt)
		self.endTime_edit.setTime(QTime((t.hour + 2) % 24, 0))
		self.frequency_edit.addFrequencies([(frq, descr) for frq, descr, t in env.frequencies])
		self.frequency_edit.clearEditText()
		self.announce_button.clicked.connect(self.announceSession)
		self.cancel_button.clicked.connect(self.reject)

	def announceSession(self):
		beg = self.beginTime_edit.dateTime().toPyDateTime()
		end = self.endTime_edit.time().toPyTime()
		try:
			post_session(beg, end, frq=self.frequency_edit.getFrequency())
			QMessageBox.information(self, 'Session announced', 'Session successfully announced!')
			self.accept()
		except Lenny64Error as err:
			if err.srvResponse() == None:
				QMessageBox.critical(self, 'Network error', 'A network problem occured: %s' % err)
			else:
				QMessageBox.critical(self, 'Lenny64 error', 'Announcement failed.\nCheck session details and Lenny64 identification settings.')







class AboutDialog(QDialog, Ui_aboutDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.text_browser.setHtml(re.sub(version_string_placeholder, version_string, self.text_browser.toHtml()))







class RwyInfoTableModel(QAbstractTableModel):
	'''
	CAUTION: Do not build if no airport data
	'''
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.column_headers = ['RWY', 'LOC freq.', 'GS', 'Surface', 'Orientation', 'Length', 'Width', 'DTHR', 'THR elev.']
		self.runways = env.airport_data.allRunways(sortByName=True)
	
	def headerData(self, section, orientation, role):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:
				return self.column_headers[section]

	def rowCount(self, parent=None):
		return len(self.runways)

	def columnCount(self, parent=None):
		return len(self.column_headers)

	def data(self, index, role):
		if role == Qt.DisplayRole:
			rwy = self.runways[index.row()]
			col = index.column()
			width, surface = env.airport_data.physicalRunwayData(rwy.physicalRwyIndex())
			if col == 0: # 'RWY
				return rwy.name
			elif col == 1: # LOC freq.
				txt = some(rwy.LOC_freq, 'none')
				if rwy.ILS_cat != None:
					txt += ' (%s)' % rwy.ILS_cat
				return txt
			elif col == 2: # GS
				if rwy.hasILS():
					return '%.1f%% / %.1f°' % (rwy.param_FPA, degrees(atan(rwy.param_FPA / 100)))
				else:
					return 'none'
			elif col == 3: # Surface
				return surface_types.get(surface, 'Unknown')
			elif col == 4: # Orientation
				return '%s°' % rwy.orientation().read()
			elif col == 5: # Length
				return '%d m' % (rwy.length(dthr=False) / m2NM)
			elif col == 6: # Width
				return '%d m' % width
			elif col == 7: # DTHR
				return 'none' if rwy.dthr == 0 else '%d m' % rwy.dthr
			elif col == 8: # THR elev.
				return 'N/A' if env.elevation_map == None else '%.1f ft' % env.elevation(rwy.threshold())


class EnvironmentInfoDialog(QDialog, Ui_envInfoDialog):
	def __init__(self, parent=None):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.magneticDeclination_infoLabel.setText(some(env.readDeclination(), 'N/A'))
		self.radarPosition_infoLabel.setText(str(env.radarPos()))
		if env.airport_data == None:
			self.airport_tab.setEnabled(False)
		else:
			self.airportName_infoLabel.setText(env.locationName())
			self.airportElevation_infoLabel.setText('%.1f ft' % env.airport_data.field_elevation)
			table_model = RwyInfoTableModel(self)
			self.runway_tableView.setModel(table_model)
			for i in range(table_model.columnCount()):
				self.runway_tableView.resizeColumnToContents(i)
	
	def showEvent(self, event):
		racked = env.strips.count(lambda s: s.lookup(rack_detail) != None)
		boxed = env.strips.count(lambda s: s.lookup(runway_box_detail) != None)
		total = env.strips.count()
		self.rackedStrips_infoLabel.setText(str(racked))
		self.looseStrips_infoLabel.setText(str(total - racked - boxed))
		self.boxedStrips_infoLabel.setText(str(boxed))
		self.playingStrips_infoLabel.setText(str(total))
		self.xpdrLinkedStrips_infoLabel.setText(str(env.strips.count(lambda s: s.linkedAircraft() != None)))
		self.fplLinkedStrips_infoLabel.setText(str(env.strips.count(lambda s: s.linkedFPL() != None)))













class RouteSpecsLostDialog(QDialog, Ui_routeSpecsLostDialog):
	def __init__(self, parent, title, lost_specs_text):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.installEventFilter(RadioKeyEventFilter(self))
		self.setWindowTitle(title)
		self.lostSpecs_box.setText(lost_specs_text)
	
	def mustOpenStripDetails(self):
		return self.openStripDetailSheet_tickBox.isChecked()







class DiscardedStripsDialog(QDialog, Ui_discardedStripsDialog):
	def __init__(self, parent, view_model, dialog_title):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.clear_button.setIcon(QIcon(IconFile.button_clear))
		self.installEventFilter(RadioKeyEventFilter(self))
		self.setWindowTitle(dialog_title)
		self.model = view_model
		self.strip_view.setModel(view_model)
		self.clear_button.clicked.connect(self.model.forgetStrips)
		self.recall_button.clicked.connect(self.recallSelectedStrips)
		self.close_button.clicked.connect(self.accept)
	
	def recallSelectedStrips(self):
		strips = [self.model.stripAt(index) for index in self.strip_view.selectedIndexes()]
		if strips != []:
			for strip in strips:
				signals.stripRecall.emit(strip)
			self.accept()




class EditRackDialog(QDialog, Ui_editRackDialog):
	def __init__(self, parent, rack_name):
		QDialog.__init__(self, parent)
		self.setupUi(self)
		self.deleteRack_info.clear()
		self.installEventFilter(RadioKeyEventFilter(self))
		self.initial_rack_name = rack_name
		self.flagged_for_deletion = False
		self.rackName_edit.setText(self.initial_rack_name)
		self.privateRack_tickBox.setChecked(self.initial_rack_name in settings.private_racks)
		self.pickColour_button.setChoice(settings.rack_colours.get(rack_name, None))
		if rack_name == default_rack_name:
			self.rackName_edit.setEnabled(False)
			self.collectedStrips_box.setVisible(False)
			self.deleteRack_button.setEnabled(False)
			self.deleteRack_info.setText('Default rack cannot be deleted')
		else:
			self.collectsFrom_edit.setPlainText('\n'.join(atc for atc, rack in settings.ATC_collecting_racks.items() if rack == rack_name))
			self.collectAutoPrintedStrips_tickBox.setChecked(settings.auto_print_collecting_rack == self.initial_rack_name)
			self.rackName_edit.selectAll()
			self.deleteRack_button.toggled.connect(self.flagRackForDeletion)
		self.buttonBox.rejected.connect(self.reject)
		self.buttonBox.accepted.connect(self.doOK)

	def flagRackForDeletion(self, toggle):
		if toggle:
			if env.strips.count(lambda s: s.lookup(rack_detail) == self.initial_rack_name) > 0:
				QMessageBox.warning(self, 'Non-empty rack deletion', 'Rack not empty. Strips will be reracked before deletion.')
			self.deleteRack_info.setText('Flagged for deletion')
		else:
			self.deleteRack_info.clear()
	
	def doOK(self):
		if self.deleteRack_button.isChecked():
			for strip in env.strips.listStrips(lambda s: s.lookup(rack_detail) == self.initial_rack_name):
				strip.writeDetail(recycled_detail, True)
				env.strips.repositionStrip(strip, default_rack_name)
			for atc, rack in list(settings.ATC_collecting_racks.items()):
				if rack == self.initial_rack_name:
					del settings.ATC_collecting_racks[atc]
			if settings.auto_print_collecting_rack == self.initial_rack_name:
				settings.auto_print_collecting_rack = None
			env.strips.removeRack(self.initial_rack_name)
		else: # rack NOT being deleted
			new_name = self.rackName_edit.text()
			# UPDATE SETTINGS
			if new_name != self.initial_rack_name: # renaming
				if env.strips.validNewRackName(new_name):
					env.strips.renameRack(self.initial_rack_name, new_name)
				else:
					QMessageBox.critical(parent_widget, 'Rack name error', 'Name is reserved or already used.')
					return # abort
			# private
			if self.initial_rack_name in settings.private_racks:
				settings.private_racks.remove(self.initial_rack_name)
			if self.privateRack_tickBox.isChecked():
				settings.private_racks.add(new_name)
			# colour
			new_colour = self.pickColour_button.getChoice()
			if self.initial_rack_name in settings.rack_colours:
				del settings.rack_colours[self.initial_rack_name]
			if new_colour != None:
				settings.rack_colours[new_name] = new_colour
			# collecting racks
			for atc, rack in list(settings.ATC_collecting_racks.items()):
				if rack == self.initial_rack_name:
					del settings.ATC_collecting_racks[atc]
			for atc in self.collectsFrom_edit.toPlainText().split('\n'):
				if atc != '':
					settings.ATC_collecting_racks[atc] = new_name
			if self.collectAutoPrintedStrips_tickBox.isChecked(): # should not be ticked if default rack
				settings.auto_print_collecting_rack = new_name
			elif settings.auto_print_collecting_rack == self.initial_rack_name:
				settings.auto_print_collecting_rack = None # back to default if box has been unticked
			# DONE
			signals.rackEdited.emit(self.initial_rack_name, new_name)
		self.accept()
