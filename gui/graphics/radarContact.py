
from datetime import timedelta

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QBrush, QRadialGradient

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.util import some
from data.params import Heading, StdPressureAlt, Speed, distance_flown
from data.radar import XPDR_emergency_codes
from data.conflict import Conflict, NoPath, horizontal_path
from data.instruction import Instruction
from data.strip import soft_link_detail, parsed_route_detail, \
				assigned_heading_detail, assigned_altitude_detail, assigned_speed_detail

from gui.misc import signals, selection
from gui.actions import instruct_selected_with_vector, instruct_selected_with_taxi
from gui.graphics.radarTag import RadarTagItem
from gui.graphics.miscGraphics import new_pen, withMargins, ACFT_pen_colour, \
				MeasuringToolItem, AltSpeedInstructingToolItem, TaxiInstructingToolItem


# ---------- Constants ----------

ACFT_body_size = 6
courseLine_maxLength = 50 # NM
assignment_altArc_spanAngle = 60 # degrees
inbound_route_turn_off_distance = 30 # NM

min_vertical_speed = 500 # ft/min
taxiing_maxSpeed = Speed(30) # speed above which aircraft are considered airborne

# -------------------------------



##------------------------------------##
##                                    ##
##           AIRCRAFT ITEMS           ##
##                                    ##
##------------------------------------##


# ============  ROOT ITEM (all child items follow)  ============

class AircraftItem(QGraphicsItem):
	
	def __init__(self, acft):
		QGraphicsItem.__init__(self, parent=None)
		self.radar_contact = acft
		self.setAcceptedMouseButtons(Qt.NoButton)
		# Children graphics items
		self.route_item = RouteItem(self)
		self.position_history_item = PositionHistoryItem(self)
		self.acft_body_item = AircraftBodyItem(self)
		self.vectors_item = VectorsItem(self)
		self.separation_ring_item = SeparationRingItem(self)
		self.soft_link_indicator_item = SoftLinkIndicatorItem(self)
		self.XPDR_call_indicator_item = XpdrCallIndicatorItem(self)
		self.radar_tag_item = RadarTagItem(self)
		self.selection_indicator_item = SelectionIndicatorItem(self)
	
	def updateItem(self):
		'''
		Update positions, rotations and visibility of child items and self
		'''
		selected = self.radar_contact is selection.acft
		self.setPos(self.radar_contact.coords().toQPointF())
		# self.acft_body_item always visible
		self.selection_indicator_item.setVisible(selected)
		# Update visibility of child items
		if self.radar_contact.ignored: # Ignored contact: turn off most stuff
			self.route_item.setVisible(False)
			self.position_history_item.setVisible(False)
			self.vectors_item.setVisible(False)
			self.separation_ring_item.setVisible(False)
			self.soft_link_indicator_item.setVisible(False)
			self.XPDR_call_indicator_item.setVisible(False)
			self.radar_tag_item.setVisible(False)
		else: # Regular case: radar visible and not ignored
			strip = env.linkedStrip(self.radar_contact)
			self.position_history_item.setVisible(True)
			self.position_history_item.updateHistory()
			self.route_item.setVisible(Conflict.DEPENDS_ON_ALT <= self.radar_contact.conflict <= Conflict.PATH_CONFLICT \
				or self.scene().show_all_routes \
				or selected and self.scene().show_selected_ACFT_assignments)
			self.route_item.updateRouteItem()
			self.separation_ring_item.setVisible(self.scene().show_separation_rings \
				or self.radar_contact.conflict >= Conflict.DEPENDS_ON_ALT)
			# Course line
			hdg = self.radar_contact.heading()
			if hdg == None or self.radar_contact.considerOnGround():
				self.vectors_item.setVisible(False)
			else: # consider airborne
				ass_hdg = None if strip == None else strip.lookup(assigned_heading_detail)
				self.vectors_item.setRotation(some(ass_hdg, hdg).trueAngle())
				self.vectors_item.setVisible(self.scene().show_all_vectors \
					or selected and self.scene().show_selected_ACFT_assignments)
			# Other
			try:
				sl_strip = env.strips.findStrip(lambda s: s.lookup(soft_link_detail) is self.radar_contact)
				self.soft_link_indicator_item.setVisible(sl_strip.linkedAircraft() is not self.radar_contact)
			except StopIteration:
				self.soft_link_indicator_item.setVisible(False)
			self.XPDR_call_indicator_item.setVisible(self.radar_contact.xpdrIdent() \
					or self.radar_contact.xpdrCode() in XPDR_emergency_codes)
			self.radar_tag_item.setVisible(self.scene().show_unlinked_tags or strip != None)
			if self.radar_tag_item.isVisible():
				self.radar_tag_item.updateInfoText()
		
	def boundingRect(self):
		return QRectF()
	
	def paint(self, painter, option, widget):
		pass
	
	def updateAfterGeneralSettingsChanged(self):
		self.separation_ring_item.updateFromSettings()
		self.radar_tag_item.updateInfoText()
		self.position_history_item.updateHistory()
	
	def updateAfterLocalSettingsChanged(self):
		self.position_history_item.updateHistory()






# ============  BODY AND SPEED VECTOR LINE  ============


class AircraftBodyItem(QGraphicsItem):
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.radar_contact = parentAircraftItem.radar_contact
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setAcceptedMouseButtons(Qt.LeftButton | Qt.MiddleButton)
		self.setCursor(Qt.PointingHandCursor)
		# Children graphics items
		self.heading_instructor = MeasuringToolItem(self)
		self.altSpeed_instructor = AltSpeedInstructingToolItem(self.radar_contact, self)
		self.taxi_instructor = TaxiInstructingToolItem(parentAircraftItem) # made sibling not to ignore transformations
		self.mouse_instruction_aborted = False
		
	def boundingRect(self):
		# includes margins around the body for easier mouse click
		return QRectF(-1.5 * ACFT_body_size, -1.5 * ACFT_body_size, 3 * ACFT_body_size, 3 * ACFT_body_size)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(ACFT_pen_colour(self.radar_contact)))
		if env.radar.missedOnLastScan(self.radar_contact.identifier):
			painter.drawText(self.boundingRect(), Qt.AlignCenter, '?')
		elif self.radar_contact.ignored:
			painter.drawText(self.boundingRect(), Qt.AlignCenter, 'X')
		elif self.radar_contact.frozen:
			painter.drawText(self.boundingRect(), Qt.AlignCenter, '=')
		elif not self.radar_contact.spawned:
			painter.drawText(self.boundingRect(), Qt.AlignCenter, '+')
		else:
			rect = QRectF(-ACFT_body_size / 2, -ACFT_body_size / 2, ACFT_body_size, ACFT_body_size)
			# solid fill if linked to a strip
			if env.linkedStrip(self.radar_contact) != None:
				painter.setBrush(QBrush(painter.pen().color()))
			if self.radar_contact.xpdrOn():
				painter.drawRect(rect)
			else: # primary target
				painter.drawEllipse(rect)

	## MOUSE EVENTS
	
	def mouseInstructionInProgress(self):
		return self.heading_instructor.isVisible() or self.altSpeed_instructor.isVisible() or self.taxi_instructor.isVisible()
	
	def mousePressEvent(self, event):
		QGraphicsItem.mousePressEvent(self, event)
		if event.button() == Qt.LeftButton:
			self.mouse_instruction_aborted = False
			selection.selectAircraft(self.radar_contact)
			event.accept()
		elif event.button() == Qt.RightButton and self.mouseInstructionInProgress(): # Abort mouse instruction
			self.mouse_instruction_aborted = True
			if self.heading_instructor.isVisible():
				self.heading_instructor.stop(False)
			if self.altSpeed_instructor.isVisible():
				self.altSpeed_instructor.setVisible(False)
			if self.taxi_instructor.isVisible():
				self.taxi_instructor.stop()
			event.accept()
		elif event.button() == Qt.MiddleButton:
			if event.modifiers() & Qt.ShiftModifier:
				selection.unlinkAircraft(self.radar_contact)
			else:
				selection.linkAircraft(self.radar_contact)
			event.accept()
	
	def mouseMoveEvent(self, event):
		if event.buttons() & Qt.LeftButton:
			# Start the measuring tool if none is already visible (unless one was already aborted)
			if not (self.mouseInstructionInProgress() or self.mouse_instruction_aborted) \
					and (settings.session_manager.session_type == SessionType.TEACHER or env.linkedStrip(self.radar_contact) != None):
				if event.modifiers() & Qt.ShiftModifier:
					self.altSpeed_instructor.setVisible(True)
				else:
					if self.radar_contact.considerOnGround():
						self.taxi_instructor.start(self.radar_contact)
					else:
						self.heading_instructor.start(False)
				event.accept()
			# Update current tool with new position if any
			if self.heading_instructor.isVisible():
				self.heading_instructor.updateMouseXY(event.pos())
			if self.altSpeed_instructor.isVisible():
				self.altSpeed_instructor.updateMouseXY(event.pos())
			if self.taxi_instructor.isVisible():
				self.taxi_instructor.updateMouseXY(event.scenePos())
		QGraphicsItem.mouseMoveEvent(self, event)
	
	def mouseReleaseEvent(self, event):
		QGraphicsItem.mouseReleaseEvent(self, event)
		if event.button() == Qt.LeftButton:
			instr = None
			if self.heading_instructor.isVisible():
				hdg = self.heading_instructor.measuredHeading().rounded(False, step=5)
				instr = Instruction(Instruction.VECTOR_HDG, arg=hdg)
				self.heading_instructor.stop(False)
			if self.altSpeed_instructor.isVisible():
				if self.altSpeed_instructor.altMode(): # Altitude mode
					alt = self.altSpeed_instructor.altitudeInstruction()
					instr = Instruction(Instruction.VECTOR_ALT, arg=alt) # str
				else: # Speed mode
					spd = self.altSpeed_instructor.speedInstruction().rounded()
					instr = Instruction(Instruction.VECTOR_SPD, arg=spd)
				self.altSpeed_instructor.setVisible(False)
			if instr != None:
				selection.writeStripAssignment(instr)
				instruct_selected_with_vector(instr)
			if self.taxi_instructor.isVisible():
				if self.taxi_instructor.instructionSnappedToGround(): # ground net node list or parking position
					route, pk = self.taxi_instructor.taxiRouteInstruction()
					instruct_selected_with_taxi(Instruction(Instruction.TAXI, arg=(route, pk)))
				self.taxi_instructor.stop()

	def mouseDoubleClickEvent(self, event):
		if event.button() == Qt.LeftButton:
			if event.modifiers() & Qt.ShiftModifier: # Clear assignments
				if selection.strip != None:
					selection.strip.clearVectors()
					signals.stripInfoChanged.emit()
			else:
				if selection.strip != None:
					signals.stripEditRequest.emit(selection.strip)
			event.accept()
		else:
			QGraphicsItem.mouseDoubleClickEvent(self, event)






class PositionHistoryItem(QGraphicsItem):
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setVisible(False)
		self.radar_contact = parentAircraftItem.radar_contact
		self.history = [] # points in local coordinate system
		self.bbox = QRectF()
	
	def updateHistory(self):
		past_coords = self.radar_contact.positionHistory(settings.radar_contact_trace_time)
		self.history = [coords.toQPointF() - self.parentItem().pos() for coords in past_coords]
		self.prepareGeometryChange()
		self.bbox = QRectF()
		for p in self.history:
			self.bbox |= withMargins(QRectF(p, p), 1)
	
	def boundingRect(self):
		return self.bbox

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(ACFT_pen_colour(self.radar_contact), style=Qt.DotLine))
		prev = QPointF(0, 0)
		for p in reversed(self.history):
			painter.drawLine(prev, p)
			prev = p





# ============  ASSIGNMENTS  ============


class VectorsItem(QGraphicsItem):
	'''
	Draws the all-in-one vector&error graphics.
	'''
	bad_speed_mark_hv_offset = .15 # Horizontal and vertical projected length of bad speed tick mark outer ends
	
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setVisible(False)
		self.radar_contact = parentAircraftItem.radar_contact
	
	def boundingRect(self):
		half = 2 + courseLine_maxLength
		return QRectF(-half, -half, 2 * half, 2 * half)

	def paint(self, painter, option, widget):
		strip = env.linkedStrip(self.radar_contact)
		conflicts = {} if strip == None else strip.vectoringConflicts(env.QNH())
		cur_speed = self.radar_contact.groundSpeed()
		if cur_speed != None and cur_speed.diff(taxiing_maxSpeed) > 0:
			if assigned_speed_detail in conflicts:
				diff_speed = conflicts[assigned_speed_detail]
				assume_h_speed = cur_speed - diff_speed
				speed_marks_tip_sign = -1 if diff_speed < 0 else 1
				speed_marks_pen = new_pen(settings.colour('assignment_bad'), width=2)
			else:
				assume_h_speed = cur_speed
				speed_marks_tip_sign = 0
				speed_marks_pen = new_pen(settings.colour('assignment_OK'))
			## Course line
			hdg_line_length = min(courseLine_maxLength, distance_flown(timedelta(minutes=self.scene().speedMarkCount()), assume_h_speed))
			hdg_line_colour = settings.colour('assignment_bad' if assigned_heading_detail in conflicts else 'assignment_OK')
			hdg_line_style = Qt.DotLine if strip == None or strip.lookup(assigned_heading_detail) == None else Qt.SolidLine
			painter.setPen(new_pen(hdg_line_colour, style=hdg_line_style))
			painter.drawLine(0, 0, 0, -hdg_line_length)
			## Speed tick marks
			painter.setPen(speed_marks_pen)
			d_1min = distance_flown(timedelta(minutes=1), assume_h_speed)
			for i in range(1, self.scene().speedMarkCount() + 1):
				d_mid = i * d_1min # tick mark distance
				d_tip = d_mid + speed_marks_tip_sign * VectorsItem.bad_speed_mark_hv_offset
				painter.drawLine(QPointF(0, -d_mid), QPointF(-VectorsItem.bad_speed_mark_hv_offset, -d_tip))
				painter.drawLine(QPointF(0, -d_mid), QPointF(VectorsItem.bad_speed_mark_hv_offset, -d_tip))
			## Altitude arc
			if assigned_altitude_detail in conflicts:
				vs = self.radar_contact.verticalSpeed()
				if vs == None or abs(vs) < min_vertical_speed:
					vs = min_vertical_speed
				ttr_alt = timedelta(minutes = abs(conflicts[assigned_altitude_detail]) / vs) # time to reach alt
				arc_dist = distance_flown(ttr_alt, assume_h_speed) # ground speed this time
				if arc_dist > hdg_line_length:
					arc_dist = hdg_line_length
					alt_arc_style = Qt.DotLine
				else:
					alt_arc_style = Qt.SolidLine
				painter.setPen(new_pen(settings.colour('assignment_bad'), style=alt_arc_style))
				arc_rect = QRectF(-arc_dist, -arc_dist, 2*arc_dist, 2*arc_dist)
				painter.drawArc(arc_rect, 16 * (90 - assignment_altArc_spanAngle / 2), 16 * assignment_altArc_spanAngle)






class RouteItem(QGraphicsItem):
	'''
	Draws the assigned route if any, or the conflicting path (route or vectored heading) if there is a conflict.
	'''
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setVisible(False)
		self.radar_contact = parentAircraftItem.radar_contact
		self.bounding_rect = QRectF()
		self.lines = []
		self.colour = None # None if should not be drawn
	
	def updateRouteItem(self):
		self.colour = None
		hshape = []
		try:
			if Conflict.DEPENDS_ON_ALT <= self.radar_contact.conflict <= Conflict.PATH_CONFLICT:
				hshape = horizontal_path(self.radar_contact, hdg=True, rte=True, ttf=settings.route_conflict_anticipation)
				self.colour = settings.colour(separation_ring_colour_names[self.radar_contact.conflict])
			else:
				strip = env.linkedStrip(self.radar_contact)
				if strip != None:
					hshape = horizontal_path(self.radar_contact, hdg=False, rte=True)
					if self.radar_contact is selection.acft:
						draw = True
						if not self.scene().show_all_routes and env.airport_data != None: # check if inbound and should turn off route
							route = strip.lookup(parsed_route_detail)
							if route != None and route.arr.code == env.airport_data.navpoint.code: # inbound; turn off if too close on last leg
								pos = self.radar_contact.coords()
								if pos.distanceTo(route.arr.coordinates) < inbound_route_turn_off_distance:
									draw = route.currentLegIndex(pos) != route.legCount() - 1
						if draw:
							self.colour = settings.colour('route_followed' if strip.lookup(assigned_heading_detail) == None else 'route_overridden')
					elif self.scene().show_all_routes:
						self.colour = ACFT_pen_colour(self.radar_contact)
		except NoPath:
			pass
		p_offset = self.parentItem().pos()
		self.lines = [(p1.toQPointF() - p_offset, p2.toQPointF() - p_offset) for p1, p2 in hshape]
		self.prepareGeometryChange()
		self.bounding_rect = QRectF(-1, -1, 2, 2)
		for p1, p2 in self.lines:
			self.bounding_rect |= QRectF(p1, p2)
		
	def boundingRect(self):
		return self.bounding_rect

	def paint(self, painter, option, widget):
		if self.colour != None:
			painter.setPen(new_pen(self.colour, style=Qt.DashLine))
			for p1, p2 in self.lines:
				painter.drawLine(p1, p2)















# ============  MISC. INDICATORS  ============


class XpdrCallIndicatorItem(QGraphicsItem):
	'''
	Draws the indicator appearing on transponder IDENT or EMG squawk code.
	'''
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setVisible(False)
		self.setRotation(45)
		
	def boundingRect(self):
		w = 10 + ACFT_body_size
		return QRectF(-w / 2, -w / 2, w, w)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour('XPDR_call'), width=3))
		painter.drawRect(self.boundingRect())





class SoftLinkIndicatorItem(QGraphicsItem):
	'''
	Draws the indicator appearing on ACFT identification from strip SQ assignments.
	'''
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setVisible(False)
		
	def boundingRect(self):
		w = 5 * ACFT_body_size
		return QRectF(-w / 2, -w / 2, w, w)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour('XPDR_identification'), width=2))
		for i in range(3):
			w = (i + 2) * ACFT_body_size
			painter.drawRect(-w / 2, -w / 2, w, w)




class SelectionIndicatorItem(QGraphicsItem):
	'''
	Draws the ACFT selection indicator around the body.
	'''
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setVisible(False)
		
	def boundingRect(self):
		w = 20 + ACFT_body_size
		return QRectF(-w / 2, -w / 2, w, w)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour('selection_indicator'), width=2))
		painter.drawEllipse(self.boundingRect())





separation_ring_colour_names = {
	Conflict.NO_CONFLICT: 'separation_ring_OK',
	Conflict.DEPENDS_ON_ALT: 'separation_ring_warning',
	Conflict.PATH_CONFLICT: 'separation_ring_bad',
	Conflict.NEAR_MISS: 'assignment_bad'
}

class SeparationRingItem(QGraphicsItem):
	'''
	Draws the separation rings, whose colour will depend on conflict status.
	Also draws closer circles near the ACFT body if there is a conflict.
	'''
	def __init__(self, parentAircraftItem):
		QGraphicsItem.__init__(self, parentAircraftItem)
		self.setVisible(False)
		self.radar_contact = parentAircraftItem.radar_contact
		self.sep_range = settings.horizontal_separation
		
	def boundingRect(self):
		return QRectF(-self.sep_range / 2, -self.sep_range / 2, self.sep_range, self.sep_range)

	def paint(self, painter, option, widget):
		c = self.radar_contact.conflict
		if self.scene().show_separation_rings or c >= Conflict.DEPENDS_ON_ALT: # Draw separation rigns
			pen_width = 2 if c == Conflict.NEAR_MISS else 0
			painter.setPen(new_pen(settings.colour(separation_ring_colour_names[c]), width=pen_width))
			painter.drawEllipse(self.boundingRect())
			if c >= Conflict.DEPENDS_ON_ALT: # Draw conflict indicators (closer to ACFT bodies)
				for r in [.25, .3, .35]:
					painter.drawEllipse(QRectF(-r, -r, 2 * r, 2 * r))
	
	def updateFromSettings(self):
		if self.sep_range != settings.horizontal_separation:
			self.prepareGeometryChange()
			self.sep_range = settings.horizontal_separation


