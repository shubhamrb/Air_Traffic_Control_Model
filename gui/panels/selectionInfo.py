
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon
from ui.selectionInfoPane import Ui_selectionInfoPane
from ui.selectionInfoToolbarWidget import Ui_selectionInfoToolbarWidget

from session.env import env
from session.config import settings

from data.strip import parsed_route_detail
from data.coords import dist_str
from data.params import TTF_str

from gui.misc import signals, selection, IconFile
from gui.dialog.routeDialog import RouteDialog


# ---------- Constants ----------

# -------------------------------




class SelectionInfoWidget:
	'''
	CAUTION inheriting objects MUST:
	- inherit from QWidget
	- contain two-state toggle widgets named "cheatContact_toggle" and "ignoreContact_toggle"
	- define method "updateDisplay"
	'''
	
	def __init__(self):
		self.radar_contact = None
		self.updateSelection()
		self.cheatContact_toggle.clicked.connect(self.setContactCheatMode)
		self.ignoreContact_toggle.clicked.connect(self.setContactIgnore)
		env.radar.blip.connect(self.updateDisplay)
		signals.selectionChanged.connect(self.updateSelection)
		signals.stripInfoChanged.connect(self.updateDisplay)
		signals.localSettingsChanged.connect(self.updateDisplay) # in case of SSR capability cahnge
	
	def updateSelection(self):
		self.radar_contact = selection.acft
		if self.radar_contact == None:
			for toggle in self.cheatContact_toggle, self.ignoreContact_toggle:
				toggle.setEnabled(False)
				toggle.setChecked(False)
		else:
			self.cheatContact_toggle.setEnabled(True)
			self.ignoreContact_toggle.setEnabled(True)
			self.cheatContact_toggle.setChecked(self.radar_contact.individual_cheat)
			self.ignoreContact_toggle.setChecked(self.radar_contact.ignored)
		self.updateDisplay()
	
	def setContactCheatMode(self, b):
		if self.radar_contact != None:
			self.radar_contact.setIndividualCheat(b)
			signals.selectionChanged.emit()
	
	def setContactIgnore(self, b):
		if self.radar_contact != None:
			self.radar_contact.ignored = b
			signals.selectionChanged.emit()








class SelectionInfoToolbarWidget(QWidget, Ui_selectionInfoToolbarWidget, SelectionInfoWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		SelectionInfoWidget.__init__(self)
	
	def updateDisplay(self):
		if self.radar_contact == None:
			self.setEnabled(False)
			hdg = alt = ias = None
		else:
			self.setEnabled(True)
			hdg = self.radar_contact.heading()
			alt = self.radar_contact.xpdrAlt()
			ias = self.radar_contact.xpdrIAS()
		txt = []
		txt.append('Hdg ' + ('---' if hdg == None else hdg.read()))
		if settings.SSR_mode_capability not in '0A' or alt != None:
			txt.append('FL ' + ('---' if alt == None else '%03d' % alt.FL()))
		if settings.SSR_mode_capability == 'S' or ias != None:
			txt.append('IAS ' + ('---' if ias == None else '%d' % ias.kt))
		self.selection_info.setText(' / '.join(txt))






class SelectionInfoPane(QWidget, Ui_selectionInfoPane, SelectionInfoWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		SelectionInfoWidget.__init__(self)
		self.viewRoute_button.setIcon(QIcon(IconFile.button_view))
		self.airport_box.setEnabled(env.airport_data != None)
		self.viewRoute_button.clicked.connect(self.viewRoute)
	
	def viewRoute(self):
		if self._last_known_route != None:
			spd = acft = None
			if self.radar_contact != None:
				spd = self.radar_contact.groundSpeed()
				acft = self.radar_contact.xpdrAcftType()
			RouteDialog(self._last_known_route, speedHint=spd, acftHint=acft, parent=self).exec()
	
	def updateDisplay(self):
		if self.radar_contact == None:
			self.info_area.setEnabled(False)
			return
		else:
			self.info_area.setEnabled(True)
		
		# AIRCRAFT BOX
		# Heading
		hdg = self.radar_contact.heading()
		self.aircraftHeading_info.setText('?' if hdg == None else hdg.read() + '°')
		# Alt./FL
		alt = self.radar_contact.xpdrAlt()
		if alt == None:
			self.aircraftAltitude_info.setText('N/A' if settings.SSR_mode_capability in '0A' else '?')
		else:
			alt_str = env.readStdAlt(alt, step=None, unit=True)
			if not alt_str.startswith('FL') and env.QNH(noneSafe=False) == None:
				alt_str += '  !!QNH'
			self.aircraftAltitude_info.setText(alt_str)
		# Ground speed
		groundSpeed = self.radar_contact.groundSpeed()
		if groundSpeed == None:
			self.aircraftGroundSpeed_info.setText('?')
		else:
			self.aircraftGroundSpeed_info.setText(str(groundSpeed))
		# Indicated airspeed speed
		ias = self.radar_contact.IAS()
		if ias == None:
			self.indicatedAirSpeed_info.setText('?' if settings.SSR_mode_capability == 'S' else 'N/A')
		else:
			s = str(ias)
			if self.radar_contact.xpdrIAS() == None:
				s += '  !!estimate'
			self.indicatedAirSpeed_info.setText(s)
		# Vertical speed
		vs = self.radar_contact.verticalSpeed()
		if vs == None:
			self.aircraftVerticalSpeed_info.setText('N/A' if settings.SSR_mode_capability in '0A' else '?')
		else:
			self.aircraftVerticalSpeed_info.setText('%+d ft/min' % vs)
		
		# ROUTE BOX
		coords = self.radar_contact.coords()
		strip = env.linkedStrip(self.radar_contact)
		route = None if strip == None else strip.lookup(parsed_route_detail)
		self._last_known_route = route
		if route == None:
			self.route_box.setEnabled(False)
		else:
			self.route_box.setEnabled(True)
			i_leg = route.currentLegIndex(coords)
			wpdist = coords.distanceTo(route.waypoint(i_leg).coordinates)
			self.legCount_info.setText('%d of %d' % (i_leg + 1, route.legCount()))
			self.legSpec_info.setText(route.legStr(i_leg))
			self.waypointAt_info.setText(dist_str(wpdist))
			try: # TTF
				if groundSpeed == None:
					raise ValueError('No ground speed info')
				self.waypointTTF_info.setText(TTF_str(wpdist, groundSpeed))
			except ValueError:
				self.waypointTTF_info.setText('?')
		
		# AIRPORT BOX
		if env.airport_data != None:
			airport_dist = coords.distanceTo(env.radarPos())
			self.airportBearing_info.setText(coords.headingTo(env.radarPos()).read())
			self.airportDistance_info.setText(dist_str(airport_dist))
			try: # TTF
				if groundSpeed == None:
					raise ValueError('No ground speed info')
				self.airportTTF_info.setText(TTF_str(airport_dist, groundSpeed))
			except ValueError:
				self.airportTTF_info.setText('?')
		
