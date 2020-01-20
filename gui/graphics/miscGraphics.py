from PyQt5.QtCore import Qt, QRect, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PyQt5.QtGui import QTransform, QPainterPath, QPen, QFontMetrics, QIcon, QPixmap

from session.config import settings
from session.env import env

from data.util import some, bounded
from data.strip import rack_detail
from data.coords import EarthCoords, RadarCoords, dist_str
from data.params import StdPressureAlt, Speed

from gui.misc import signals
from ext.resources import pixmap_corner_sep


# ---------- Constants ----------

altitude_sensitivity = 40 # NM to ft
speed_sensitivity = 1 # NM to kt

speedInstruction_defaultZeroCursor = Speed(200)

min_speed_instruction = 80
max_speed_instruction = 800
taxi_tool_snap_dist = .1 # NM
groundnet_pos_taxi_precision = .03 # NM
min_taxi_drag = .02 # NM

text_label_max_rect = QRect(-100, -40, 200, 80)

# -------------------------------


def withMargins(rect, margin):
	return QRectF(rect.topLeft() - QPointF(margin, margin), rect.bottomRight() + QPointF(margin, margin))




def new_pen(colour, width=0, style=Qt.SolidLine):
	'''
	Returns a cosmetic (unaffected by zoom) pen with given colour, width and style.
	Default is thin solid line.
	'''
	pen = QPen(style)
	pen.setColor(colour)
	pen.setWidth(width)
	pen.setCosmetic(True)
	return pen


def coloured_square_icon(colour, width=32):
	pixmap = QPixmap(width, width)
	pixmap.fill(colour)
	return QIcon(pixmap)



class EmptyGraphicsItem(QGraphicsItem):
	'''
	Useful for "layers"
	Probably an ugly replacement but mouse gestures were not passed down with QGraphicsItemGroup
	'''
	def __init__(self):
		QGraphicsItem.__init__(self, None)
	
	def boundingRect(self):
		return QRectF()
	
	def paint(self, painter, option, widget):
		pass




def ACFT_pen_colour(radar_contact):
	if radar_contact.ignored:
		return settings.colour('ACFT_ignored')
	strip = env.linkedStrip(radar_contact)
	if strip != None: # look for strip position colour (rack colour, overrides range colour)
		rack = strip.lookup(rack_detail)
		if rack != None and rack in settings.rack_colours:
			return settings.rack_colours[rack]
	sq = radar_contact.xpdrCode()
	if sq != None: # look for a range colour
		try:
			return next(rng for rng in settings.XPDR_assignment_ranges if rng.lo <= sq <= rng.hi and rng.col != None).col
		except StopIteration:
			pass # no range colour available
	return settings.colour('ACFT_unlinked') if strip == None else settings.colour('ACFT_linked')








class MouseOverLabelledItem(QGraphicsItem):
	def __init__(self, graphics_item, lbl_colour_name, pin_layer):
		'''
		pin_layer == None: label cannot be pinned
		WARNING: better for text label placement if child graphics item is centred around 0,0
		'''
		QGraphicsItem.__init__(self, parent=None)
		self.child_item = graphics_item
		self.child_item.setParentItem(self)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, self.child_item.flags() & QGraphicsItem.ItemIgnoresTransformations)
		self.label_item = MouseOverTextLabelItem(self, lbl_colour_name)
		self.label_item.setPos(0, self.child_item.boundingRect().top())
		self.label_item.setVisible(False)
		self.setAcceptHoverEvents(True)
		self.pin_layer = pin_layer
	
	def setMouseOverText(self, text):
		self.label_item.setLabelText(text)
	
	def pinLabel(self, toggle):
		assert self.pin_layer != None
		self.setAcceptHoverEvents(not toggle)
		self.label_item.setPlacedAbove(not toggle)
		self.label_item.setVisible(toggle)
		if toggle:
			self.label_item.setPos(0, self.child_item.boundingRect().bottom())
			self._backup_parent = self.parentItem()
			self.setParentItem(self.pin_layer)
		else:
			self.label_item.setPos(0, self.child_item.boundingRect().top())
			self.setParentItem(self._backup_parent)
			if not self.parentItem().isVisible():
				# Below is not really elegant, but visibility update required when backup parent layer not visible
				self.parentItem().setVisible(True)
				self.parentItem().setVisible(False)
	
	def pinned(self):
		return not self.acceptHoverEvents()
	
	def hoverEnterEvent(self, event):
		self.label_item.setVisible(True)
	
	def hoverLeaveEvent(self, event):
		self.label_item.setVisible(False)
	
	def mouseDoubleClickEvent(self, event):
		if self.pin_layer != None and event.button() == Qt.LeftButton and not event.modifiers() & Qt.ShiftModifier:
			self.pinLabel(not self.pinned())
		else:
			QGraphicsItem.mouseDoubleClickEvent(self, event)
	
	def boundingRect(self):
		return self.child_item.boundingRect()
		
	def paint(self, painter, option, widget):
		pass



class MouseOverTextLabelItem(QGraphicsItem):
	margin = 2
	
	def __init__(self, parentItem, colour_name):
		QGraphicsItem.__init__(self, parentItem)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.text = ''
		self.colour_name = colour_name
		self.placed_above = True
	
	def setPlacedAbove(self, b):
		self.placed_above = b
		self.prepareGeometryChange()
	
	def setLabelText(self, text):
		self.text = text
		self.prepareGeometryChange()
	
	def boundingRect(self):
		rect = QRectF(QFontMetrics(self.scene().font()).boundingRect(text_label_max_rect, Qt.AlignCenter, self.text))
		width = rect.width() + 2 * MouseOverTextLabelItem.margin
		height = rect.height() + 2 * MouseOverTextLabelItem.margin
		top_coord = -height if self.placed_above else 0
		return QRectF(-width / 2, top_coord, width, height)
		
	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour(self.colour_name)))
		painter.drawText(self.boundingRect(), Qt.AlignCenter, self.text)




















##------------------------------------##
##                                    ##
##          BACKGROUND IMAGES         ##
##                                    ##
##------------------------------------##

class BgPixmapItem(QGraphicsPixmapItem):
	def __init__(self, src, title, pixmap, NW_coords, SE_coords):
		QGraphicsPixmapItem.__init__(self, pixmap, None)
		self.source_file = src
		self.title = title
		rect = self.boundingRect()
		nw = NW_coords.toQPointF()
		se = SE_coords.toQPointF()
		scale = QTransform.fromScale((se.x() - nw.x()) / rect.width(), (se.y() - nw.y()) / rect.height())
		self.setTransform(scale)
		self.setPos(nw)
		self.setVisible(False)
	
	def NWcoords(self):
		return EarthCoords.fromRadarCoords(RadarCoords.fromQPointF(self.scenePos()))
	
	def SEcoords(self):
		return EarthCoords.fromRadarCoords(RadarCoords.fromQPointF(self.mapToScene(self.boundingRect().bottomRight())))
	
	def specLine(self):
		nw = self.NWcoords()
		se = self.SEcoords()
		return '%s\t%.8f,%.8f%s%.8f,%.8f\t%s' % (self.source_file, nw.lat, nw.lon, pixmap_corner_sep, se.lat, se.lon, self.title)




class BgHandDrawingItem(QGraphicsItem):
	def __init__(self, src, title, draw_sections):
		QGraphicsItem.__init__(self, None)
		self.source_file = src
		self.title = title
		self.bounding_rect = QRectF()
		self.line_paths = []
		self.single_points = []
		self.text_labels = []
		for colour, points in draw_sections:
			for coords, txt in points:
				if txt != None:
					label_item = BgHandDrawingLabelItem(colour, txt, self)
					self.text_labels.append(label_item)
					label_item.setPos(self.qpoint_rebound(coords))
			if len(points) == 1:
				point_item = BgHandDrawingPointItem(colour, self)
				self.single_points.append(point_item)
				point_item.setPos(self.qpoint_rebound(points[0][0]))
			else:
				path = QPainterPath()
				path.moveTo(self.qpoint_rebound(points[0][0]))
				for p, txt in points[1:]:
					path.lineTo(self.qpoint_rebound(p))
				self.line_paths.append((colour, path))
		self.setVisible(False)
	
	def repositionable(self):
		return False
	
	def qpoint_rebound(self, coords):
		p = coords.toQPointF()
		self.bounding_rect |= QRectF(p - QPointF(10, 10), p + QPointF(10, 10))
		return p
	
	def boundingRect(self):
		return self.bounding_rect | self.childrenBoundingRect()

	def paint(self, painter, option, widget):
		for colour, path in self.line_paths:
			painter.setPen(new_pen(colour))
			painter.drawPath(path)
	
	def specLine(self):
		return '%s\tDRAW\t%s' % (self.source_file, self.title)



class BgHandDrawingLabelItem(QGraphicsItem):	
	def __init__(self, colour, text, parent_drawing):
		QGraphicsItem.__init__(self, parent_drawing)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.colour = colour
		self.text = text
		
	def boundingRect(self):
		return QRectF(-30, -4, 60, 8)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(self.colour))
		painter.drawText(QPointF(2, 0), self.text) # STYLE text bounding rect???



class BgHandDrawingPointItem(QGraphicsItem):	
	def __init__(self, colour, parent_drawing):
		QGraphicsItem.__init__(self, parent_drawing)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.colour = colour
		
	def boundingRect(self):
		return QRectF(-2, -2, 4, 4)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(self.colour))
		painter.drawLine(QPointF(-2, -2), QPointF(2, 2))
		painter.drawLine(QPointF(-2, 2), QPointF(2, -2))






##------------------------------------##
##                                    ##
##            CUSTOM LABELS           ##
##                                    ##
##------------------------------------##


class CustomLabelItem(QGraphicsItem):
	def __init__(self, text):
		QGraphicsItem.__init__(self, None)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setAcceptedMouseButtons(Qt.LeftButton)
		self.display_text = text
	
	def label(self):
		return self.display_text
	
	def earthCoords(self):
		return EarthCoords.fromRadarCoords(RadarCoords.fromQPointF(self.scenePos()))

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour('measuring_tool')))
		painter.drawText(self.boundingRect(), Qt.AlignCenter, self.display_text) #STYLE text bounding rect
		
	def boundingRect(self):
		return QRectF(-50, -10, 100, 20)
	
	def mouseDoubleClickEvent(self, event):
		if event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier:
			event.accept()
			self.scene().removeItem(self)
		else:
			QGraphicsItem.mouseDoubleClickEvent(self, event)







##------------------------------------##
##                                    ##
##             MOUSE TOOLS            ##
##                                    ##
##------------------------------------##



class ToolTextItem(QGraphicsItem):
	#STATIC
	rectangle = QRectF(-50, -15, 100, 30) #STYLE programmatic text bounding rect
	
	def __init__(self, parentMToolItem):
		QGraphicsItem.__init__(self, parentMToolItem)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.display_text = ''
	
	def updateText(self, txt):
		self.display_text = txt
		self.update(self.boundingRect())

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(settings.colour('measuring_tool')))
		painter.drawText(ToolTextItem.rectangle, Qt.AlignCenter, self.display_text)
		
	def boundingRect(self):
		return ToolTextItem.rectangle





class MeasuringToolItem(QGraphicsItem):
	def __init__(self, parent=None):
		QGraphicsItem.__init__(self, parent)
		self.display_distance = True
		self.setVisible(False)
		self.info_box = ToolTextItem(self)
		self.setCursor(Qt.CrossCursor)
		self.mousePos = self.pos() # dummy

	def paint(self, painter, option, widget):
		# Draw measuring line; the text box draws itslef
		painter.setPen(new_pen(settings.colour('measuring_tool')))
		painter.drawLine(QPointF(0, 0), self.mousePos)
		
	def boundingRect(self):
		return withMargins(QRectF(QPointF(0, 0), self.mousePos).normalized(), 10)
	
	def start(self, display_dist):
		self.display_distance = display_dist
		self.prepareGeometryChange()
		self.mousePos = QPointF(0, 0)
		self.info_box.updateText('')
		self.setVisible(True)
	
	def stop(self, emit_measured_signal):
		self.setVisible(False)
		if emit_measured_signal:
			signals.hdgDistMeasured.emit(self.measuredHeading(), self.measuredDistance())
		
	def updateMouseXY(self, mouseXY):
		self.prepareGeometryChange()
		self.mousePos = mouseXY
		txt = '%s°' % self.measuredHeading().read()
		if self.display_distance:
			txt += '\n%s' % dist_str(self.measuredDistance())
		self.info_box.updateText(txt)
		self.info_box.setPos(self.mousePos / 2)
	
	def measuredDistance(self):
		return RadarCoords(0, 0).distanceTo(RadarCoords.fromQPointF(self.mousePos))
	
	def measuredHeading(self):
		return RadarCoords(0, 0).headingTo(RadarCoords.fromQPointF(self.mousePos))









class AltSpeedInstructingToolItem(QGraphicsItem):
	def __init__(self, radar_contact, parent_item):
		QGraphicsItem.__init__(self, parent_item)
		self.setVisible(False)
		self.info_box = ToolTextItem(self)
		self.info_box.setPos(ToolTextItem.rectangle.topLeft() / 2)
		self.radar_contact = radar_contact
		self.mouseXY = QPointF(0, 0)
		self.diff_alt_measured = None
		self.diff_speed_measured = None
		
	def paint(self, painter, option, widget):
		# Draw measuring line; the text box draws itslef
		painter.setPen(new_pen(settings.colour('measuring_tool')))
		if self.altMode():
			painter.drawLine(QPointF(0, 0), QPointF(0, self.mouseXY.y()))
		else: # Speed mode
			painter.drawLine(QPointF(0, 0), QPointF(self.mouseXY.x(), 0))
		
	def boundingRect(self):
		return withMargins(QRectF(QPointF(0, 0), self.mouseXY).normalized(), 10)
		
	def updateMouseXY(self, localXY):
		self.prepareGeometryChange()
		self.mouseXY = localXY
		if self.altMode():
			self.diff_alt_measured = -altitude_sensitivity * self.mouseXY.y()
			self.diff_speed_measured = None
			txt = self.altitudeInstruction()
		else: # Speed mode
			self.diff_alt_measured = None
			self.diff_speed_measured = speed_sensitivity * self.mouseXY.x()
			txt = 'IAS %s' % self.speedInstruction()
		self.info_box.updateText(txt)
	
	def altitudeInstruction(self):
		qnh = env.QNH()
		alt = self.radar_contact.xpdrAlt()
		if alt == None:
			zero_cursor_ft = 0 if self.radar_contact.xpdrGND() else env.transitionAltitude()
		else:
			zero_cursor_ft = alt.ftAMSL(qnh)
		return env.readStdAlt(StdPressureAlt.fromAMSL(max(0, zero_cursor_ft + self.diff_alt_measured), qnh), step=5, unit=True)
	
	def speedInstruction(self):
		zero_cursor = self.radar_contact.IAS()
		if zero_cursor == None:
			zero_cursor = some(self.radar_contact.groundSpeed(), speedInstruction_defaultZeroCursor)
		return Speed(bounded(min_speed_instruction, zero_cursor.kt + self.diff_speed_measured, max_speed_instruction)).rounded(step=10)

	def altMode(self):
		return abs(self.mouseXY.x()) < abs(self.mouseXY.y())
	
	




class TaxiInstructingToolItem(QGraphicsItem):
	def __init__(self, parent_item):
		QGraphicsItem.__init__(self, parent_item)
		self.acft = None # to be given on .start
		self.setVisible(False)
		self.bbox = QRectF(0, 0, 0, 0)
		self.node_route = None # None if start/end point too far from ground net; list of nodes otherwise
		self.parking_position = None
		self.target_point = None # invalid init value; last mouse release target (EarthCoords)
		self.snapped_OK = False
		self.lines = []
	
	def boundingRect(self):
		return self.bbox
		
	def paint(self, painter, option, widget):
		# Draw taxi route; the text box draws itslef
		painter.setPen(new_pen(settings.colour('measuring_tool' if self.snapped_OK else 'assignment_bad')))
		for p1, p2 in self.lines:
			painter.drawLine(p1, p2)
	
	def start(self, acft):
		self.acft = acft
		self.setVisible(True)
	
	def stop(self):
		self.setVisible(False)
		
	def updateMouseXY(self, sceneXY):
		self.target_point = EarthCoords.fromRadarCoords(RadarCoords.fromQPointF(sceneXY))
		p_acft = self.acft.coords().toRadarCoords()
		acft_qpoint = p_acft.toQPointF()
		# Get node route sequence
		if QPointF.dotProduct(sceneXY - acft_qpoint, sceneXY - acft_qpoint) < min_taxi_drag * min_taxi_drag: # min mouse move not reached
			self.node_route = None
		else: # get route end nodes
			src_node = None
			dest_node = None
			if env.airport_data != None:
				src_node = env.airport_data.ground_net.closestNode(self.acft.coords())
				if src_node != None:
					dest_node = env.airport_data.ground_net.closestNode(self.target_point, maxdist=taxi_tool_snap_dist)
			if src_node == None or dest_node == None:
				self.node_route = None
			else:
				try:
					self.node_route = env.airport_data.ground_net.shortestTaxiRoute(src_node, dest_node, settings.taxi_instructions_avoid_runways)
					p_src = env.airport_data.ground_net.nodePosition(src_node).toRadarCoords()
					if self.node_route == []: # src and dest nodes are identical
						if p_acft.distanceTo(p_src) > groundnet_pos_taxi_precision:
							self.node_route = [src_node]
					else: # first node of list is the one following src; check if we must insert src
						p_next = env.airport_data.ground_net.nodePosition(self.node_route[0]).toRadarCoords()
						if not p_acft.isBetween(p_src, p_next, groundnet_pos_taxi_precision):
							self.node_route.insert(0, src_node)
				except ValueError: # no taxi route found
					self.node_route = None
			# Get parking position
			self.parking_position = None
			if self.node_route == None or self.node_route == []:
				d_max_snap = taxi_tool_snap_dist
			else:
				d_last_node = env.airport_data.ground_net.nodePosition(self.node_route[-1]).distanceTo(self.target_point)
				d_max_snap = min(taxi_tool_snap_dist, d_last_node)
			self.parking_position = env.airport_data.ground_net.closestParkingPosition(self.target_point, maxdist=d_max_snap)
		# Update bounding box and specify the lines to draw
		self.prepareGeometryChange()
		if self.node_route == None and self.parking_position == None:
			self.snapped_OK = False
			line_tip = sceneXY - acft_qpoint
			self.lines = [(QPointF(0, 0), line_tip)]
			self.bbox = QRectF(QPointF(0, 0), line_tip).normalized()
		else:
			self.snapped_OK = True
			self.lines = []
			self.bbox = QRectF(0, 0, 0, 0)
			prev = QPointF(0, 0)
			if self.node_route != None:
				for n in self.node_route:
					p = env.airport_data.ground_net.nodePosition(n).toQPointF() - acft_qpoint
					self.lines.append((prev, p))
					self.bbox |= QRectF(prev, p).normalized()
					prev = p
			if self.parking_position != None:
				pk_point = env.airport_data.ground_net.parkingPosition(self.parking_position).toQPointF() - acft_qpoint
				self.lines.append((prev, pk_point))
				self.bbox |= QRectF(prev, pk_point).normalized()
		self.update()
	
	def instructionSnappedToGround(self):
		return self.snapped_OK
	
	def taxiRouteInstruction(self):
			return some(self.node_route, []), self.parking_position
	
	def targetPoint(self):
		return self.target_point

