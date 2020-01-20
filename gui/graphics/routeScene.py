from PyQt5.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtGui import QPixmap, QBrush, QPen
from PyQt5.QtCore import Qt, QPointF, QRectF

from data.coords import EarthCoords, breakUpLine
from gui.graphics.miscGraphics import new_pen


# ---------- Constants ----------

world_map_pixmap = 'resources/pixmap/worldMap-equirectProj.png'
route_colour_standard = Qt.green
route_colour_selected = Qt.magenta
route_colour_departure = Qt.yellow
route_colour_arrival = Qt.red
route_leg_breakUp_length = 20 # NM

# -------------------------------


def world_split(p1, p2):
	thdg = p1.headingTo(p2).trueAngle()
	return p2.lat < p1.lat and (thdg <= 90 or thdg >= 270) or p2.lat > p1.lat and 90 <= thdg <= 270 \
		or p2.lon < p1.lon and 0 <= thdg <= 180 or p2.lon > p1.lon and thdg >= 180


class RouteLegItem(QGraphicsItem):
	def __init__(self, p1, p2, parent=None):
		QGraphicsItem.__init__(self, parent)
		self.setAcceptedMouseButtons(Qt.NoButton) # is selectable but only by explicit flag setting; no mouseclick here
		self.setFlag(QGraphicsItem.ItemIsSelectable, True)
		self.segments = breakUpLine(p1.coordinates, p2.coordinates, segmentLength=route_leg_breakUp_length)
	
	def boundingRect(self):
		return self.scene().mapBoundingRect()

	def paint(self, painter, option, widget):
		colour = route_colour_selected if self.isSelected() else route_colour_standard
		painter.setPen(new_pen(colour))
		for p1, p2 in self.segments:
			if not world_split(p1, p2):
				painter.drawLine(self.scene().scenePoint(p1), self.scene().scenePoint(p2))





class RoutePointItem(QGraphicsItem):
	def __init__(self, parent=None):
		QGraphicsItem.__init__(self, parent)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setAcceptedMouseButtons(Qt.NoButton) # is selectable but only by explicit flag setting; no mouseclick here
		self.setFlag(QGraphicsItem.ItemIsSelectable, True)
	
	def boundingRect(self):
		return QRectF(-5, -5, 10, 10)

	def paint(self, painter, option, widget):
		painter.setPen(QPen(Qt.NoPen))
		painter.setBrush(QBrush(route_colour_selected if self.isSelected() else route_colour_standard))
		painter.drawEllipse(QPointF(0, 0), 4, 4)




class RoutePointCircleItem(QGraphicsItem):
	def __init__(self, radius, colour, parent=None):
		QGraphicsItem.__init__(self, parent)
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.setAcceptedMouseButtons(Qt.NoButton) # is selectable but only by explicit flag setting; no mouseclick here
		self.setFlag(QGraphicsItem.ItemIsSelectable, True)
		self.radius = radius
		self.colour = colour
	
	def boundingRect(self):
		return QRectF(-self.radius - .5, -self.radius - .5, 2 * self.radius + 1, 2 * self.radius + 1)

	def paint(self, painter, option, widget):
		painter.setPen(new_pen(self.colour, width=2))
		painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)







class RouteScene(QGraphicsScene):
	def __init__(self, route, parent):
		QGraphicsScene.__init__(self, parent)
		self.route_points = route.routePoints() # len == legCount + 1
		background_map_item = QGraphicsPixmapItem(QPixmap(world_map_pixmap))
		rect = background_map_item.boundingRect()
		self._lon_factor = rect.width() / 360
		self._lat_factor = -rect.height() / 180
		background_map_item.setOffset(-rect.width() / 2, -rect.height() / 2)
		self.map_bounding_rect = background_map_item.boundingRect()
		self.addItem(background_map_item)
		self.point_items = []
		for p in self.route_points:
			item = RoutePointItem()
			item.setPos(self.scenePoint(p.coordinates))
			self.point_items.append(item)
			self.addItem(item)
		item = RoutePointCircleItem(3, route_colour_departure)
		item.setPos(self.scenePoint(self.route_points[0].coordinates))
		self.addItem(item)
		item = RoutePointCircleItem(5, route_colour_arrival)
		item.setPos(self.scenePoint(self.route_points[-1].coordinates))
		self.addItem(item)
		self.leg_items = []
		for i in range(route.legCount()):
			item = RouteLegItem(self.route_points[i], self.route_points[i + 1])
			self.leg_items.append(item)
			self.addItem(item)
	
	def mapBoundingRect(self):
		return self.map_bounding_rect
	
	def scenePoint(self, earthCoords):
		return QPointF(self._lon_factor * earthCoords.lon, self._lat_factor * earthCoords.lat)
	
	def setSelectedLegs(self, lst):
		for i in range(len(self.leg_items)):
			self.leg_items[i].setSelected(i in lst)
			self.point_items[i + 1].setSelected(i in lst or i + 1 in lst)

	
