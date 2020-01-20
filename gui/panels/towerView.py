

from PyQt5.QtWidgets import QWidget
from ui.towerView import Ui_towerViewControllerPane

from session.config import settings
from session.env import env
from data.coords import pitchLookAt
from data.params import Heading
from ext.fgfs import TelnetSessionThreader, initial_FOV
from gui.misc import signals, selection


# ---------- Constants ----------

tracker_interval = 35 # ms
true_panel_directions = True

# -------------------------------




def lookAt_commands(earth_coords, target_geom_alt):
	twr_pos, twr_alt = env.viewpoint()
	hdg = twr_pos.headingTo(earth_coords).trueAngle()
	pitch = pitchLookAt(twr_pos.distanceTo(earth_coords), target_geom_alt - twr_alt)
	return ['set /sim/current-view/goal-heading-offset-deg %g' % -hdg, 'set /sim/current-view/goal-pitch-offset-deg %g' % pitch]





class TowerViewControllerPane(QWidget, Ui_towerViewControllerPane):
	
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		if env.airport_data != None:
			self.runway_select.addItems([r.name for r in env.airport_data.allRunways(sortByName=True)])
		self.setEnabled(False)
		self.target_acft = None
		self.tracker = TelnetSessionThreader(self, self.lookAtTargetAircraft_commands, loopInterval=tracker_interval)
		signals.towerViewProcessToggled.connect(self.setEnabled)
		signals.towerViewProcessToggled.connect(self.tracker.stop)
		signals.sessionEnded.connect(self.tracker.stop)
		signals.mainWindowClosing.connect(self.tracker.stop)
		self.lookAtAircraft_OK_button.clicked.connect(self.lookAtSelectedAircraft)
		self.lookAtRunway_OK_button.clicked.connect(self.lookAtRunway)
		self.lookNorth_button.clicked.connect(lambda: self.lookInDirection(Heading(360, true_panel_directions)))
		self.lookSouth_button.clicked.connect(lambda: self.lookInDirection(Heading(180, true_panel_directions)))
		self.lookEast_button.clicked.connect(lambda: self.lookInDirection(Heading(90, true_panel_directions)))
		self.lookWest_button.clicked.connect(lambda: self.lookInDirection(Heading(270, true_panel_directions)))
		self.useBinoculars_button.clicked.connect(lambda: self.setFOV(initial_FOV / self.binocularsFactor_edit.value()))
		self.dropBinoculars_button.clicked.connect(lambda: self.setFOV(initial_FOV))
	
	# # # # # # # # # # # # # #
	
	def lookAtTargetAircraft_commands(self):
		if self.target_acft == None:
			return []
		else:
			return lookAt_commands(self.target_acft.liveCoords(), self.target_acft.liveGeometricAlt())
	
	# # # # # # # # # # # # # #
	
	def ensureDayLight(self):
		settings.controlled_tower_viewer.sendCmd('run timeofday noon')
	
	def updateTowerPosition(self):
		twr_pos, twr_alt = env.viewpoint()
		commands = ['set /position/latitude-deg %g' % twr_pos.lat, 'set /position/longitude-deg %g' % twr_pos.lon]
		commands.append('set /position/altitude-ft %g' % twr_alt)
		settings.controlled_tower_viewer.sendCmd(commands)
	
	def lookAtSelectedAircraft(self):
		self.target_acft = selection.acft
		if self.target_acft == None:
			self.tracker.stop()
		elif self.trackAircraft_tickBox.isChecked():
			self.tracker.start() # Does nothing to the thread if it is already running
		else:
			self.tracker.stop()
			settings.controlled_tower_viewer.sendCmd(self.lookAtTargetAircraft_commands())
		
	def lookAtRunway(self):
		rwy = env.airport_data.runway(self.runway_select.currentText())
		self.tracker.stop()
		index = self.runwayPoint_select.currentIndex()
		if index == 0: # RWY threshold
			p = rwy.threshold()
		elif index == 1: # RWY end
			p = rwy.opposite().threshold()
		settings.controlled_tower_viewer.sendCmd(lookAt_commands(p, env.elevation(p)))
	
	def lookInDirection(self, d):
		self.tracker.stop()
		commands = ['set /sim/current-view/goal-heading-offset-deg %g' % -d.trueAngle(), 'set /sim/current-view/goal-pitch-offset-deg 0']
		settings.controlled_tower_viewer.sendCmd(commands)
		self.dropBinoculars_button.clicked.connect(lambda: self.setFOV(initial_FOV))
	
	def setFOV(self, fov):
		settings.controlled_tower_viewer.sendCmd('set /sim/current-view/field-of-view %g' % fov)

	
	
