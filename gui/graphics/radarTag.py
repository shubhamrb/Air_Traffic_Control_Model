from PyQt5.QtCore import Qt, QRect, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QFontMetrics

from session.config import settings
from session.env import env
from session.manager import SessionType

from data.radar import XPDR_emergency_codes
from data.strip import parsed_route_detail, assigned_altitude_detail
from data.params import StdPressureAlt
from data.util import some
from data.fpl import FPL
from data.nav import world_navpoint_db, NavpointError

from models.cpdlc import ConnectionStatus

from gui.misc import signals, selection
from gui.graphics.miscGraphics import withMargins, new_pen, ACFT_pen_colour


# ---------- Constants ----------

vertical_speed_sensitivity = 100 # feet per minute

# -------------------------------



def infoTextLines(radar_contact, compact_display):
	strip = env.linkedStrip(radar_contact)
	
	# FL/ALT. & SPEED LINE
	ass_alt = None if strip == None else strip.lookup(assigned_altitude_detail)
	if ass_alt != None:
		try:
			ass_alt = StdPressureAlt.reformatReading(ass_alt, unit=False)
		except ValueError:
			ass_alt = None
	if settings.SSR_mode_capability in '0A':
		fl_speed_line = ''
	else: # we may hope for altitude values from XPDR
		if radar_contact.xpdrGND():
			fl_speed_line = 'GND '
		else:
			xpdr_alt = radar_contact.xpdrAlt()
			if xpdr_alt == None:
				fl_speed_line = 'alt? '
			else:
				if settings.radar_tag_interpret_XPDR_FL:
					alt_str = env.readStdAlt(xpdr_alt, unit=False)
				else:
					alt_str = '%03d' % xpdr_alt.FL()
				vs = radar_contact.verticalSpeed()
				if vs == None:
					comp_char = '-'
				elif abs(vs) < vertical_speed_sensitivity:
					comp_char = '='
				elif vs > 0:
					comp_char = '↗'
				else:
					comp_char = '↘'
				fl_speed_line = '%s %c ' % (alt_str, comp_char)
	if ass_alt != None:
		fl_speed_line += ass_alt
	fl_speed_line += '  '
	if strip != None:
		fl_speed_line += some(strip.lookup(FPL.WTC, fpl=True), '')
	speed = radar_contact.groundSpeed()
	if speed != None:
		fl_speed_line += '%03d' % speed.kt
	
	# XPDR CODE || WAYPOINT/DEST LINE
	xpdr_code = radar_contact.xpdrCode()
	emg = False if xpdr_code == None else xpdr_code in XPDR_emergency_codes
	if emg or strip == None: # Show XPDR code
		sq_wp_line = '' if xpdr_code == None else '%04o' % xpdr_code
		if emg:
			sq_wp_line += '  !!EMG'
	else:
		parsed_route = strip.lookup(parsed_route_detail)
		if parsed_route == None:
			dest = some(strip.lookup(FPL.ICAO_ARR, fpl=True), '')
			try:
				ad = world_navpoint_db.findAirfield(dest)
				sq_wp_line = '%s  %s°' % (ad.code, radar_contact.coords().headingTo(ad.coordinates).read())
			except NavpointError: # not an airport
				sq_wp_line = dest
		else: # got parsed route
			leg = parsed_route.currentLegIndex(radar_contact.coords())
			if leg == 0 and parsed_route.SID() != None:
				sq_wp_line = 'SID %s' % parsed_route.SID()
			elif leg == parsed_route.legCount() - 1 and parsed_route.STAR() != None:
				sq_wp_line = 'STAR %s' % parsed_route.STAR()
			else:
				wp = parsed_route.waypoint(leg)
				sq_wp_line = '%s  %s°' % (wp.code, radar_contact.coords().headingTo(wp.coordinates).read())
	
	result_lines = [sq_wp_line, fl_speed_line] if settings.radar_tag_FL_at_bottom else [fl_speed_line, sq_wp_line]
	
	# CALLSIGN & ACFT TYPE LINE (top line, only if NOT compact display)
	if not compact_display:
		line1 = ''
		cs = radar_contact.xpdrCallsign()
		if cs == None and strip != None:
			cs = strip.callsign(fpl=True)
		if settings.session_manager.session_type == SessionType.TEACHER:
			dl = env.cpdlc.currentDataLink(radar_contact.identifier)
		else:
			dl = None if cs == None else env.cpdlc.currentDataLink(cs)
		if dl != None:
			line1 += {ConnectionStatus.OK: '⚡ ', ConnectionStatus.EXPECTING: '[⚡] ', ConnectionStatus.PROBLEM: '!![⚡] '}[dl.status()]
		line1 += some(cs, '?')
		if strip != None and strip.lookup(FPL.COMMENTS) != None:
			line1 += '*'
		if radar_contact.xpdrIdent():
			line1 += '  !!ident'
		t = radar_contact.xpdrAcftType()
		if t == None and strip != None:
			t = strip.lookup(FPL.ACFT_TYPE, fpl=True)
		if t != None:
			line1 += '  %s' % t
		result_lines.insert(0, line1)
	
	return '\n'.join(result_lines)






















class RadarTagItem(QGraphicsItem):
	def __init__(self, acft_item):
		QGraphicsItem.__init__(self, acft_item)
		self.setVisible(False)
		self.radar_contact = acft_item.radar_contact
		self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
		self.text_box_item = TextBoxItem(self)
		self.callout_line_start = QPointF(0, 0)
		self.callout_line_end = self.text_box_item.pos() + self.text_box_item.calloutConnectingPoint()
	
	def updateInfoText(self):
		self.text_box_item.updateContents()
		self.textBoxChanged()
	
	def textBoxChanged(self):
		self.prepareGeometryChange()
		self.callout_line_end = self.text_box_item.pos() + self.text_box_item.calloutConnectingPoint()
		self.update(self.boundingRect())
		
	def paint(self, painter, option, widget):
		# Draw callout line; child text box draws itself
		pen = new_pen(settings.colour('radar_tag_line'))
		painter.setPen(pen)
		painter.drawLine(self.callout_line_start, self.callout_line_end)
		
	def boundingRect(self):
		return QRectF(self.callout_line_start, self.callout_line_end).normalized() | self.childrenBoundingRect()







class TextBoxItem(QGraphicsItem):
	max_rect = QRect(-56, -20, 112, 40)
	init_offset = QPointF(66, -34)
	dummy_contents = 'XX-ABCDE  ####\n##### xxxxx\n10000 = 10000  X####'
	dummy_contents_compact = 'XX-ABCDE\n10000  #### '
	txt_rect_2lines = QRectF() # STATIC
	txt_rect_3lines = QRectF() # STATIC
	
	def setRectanglesFromFont(font):
		TextBoxItem.txt_rect_2lines = QRectF(QFontMetrics(font).boundingRect(TextBoxItem.max_rect, Qt.AlignLeft, TextBoxItem.dummy_contents_compact))
		TextBoxItem.txt_rect_3lines = QRectF(QFontMetrics(font).boundingRect(TextBoxItem.max_rect, Qt.AlignLeft, TextBoxItem.dummy_contents))
	
	def __init__(self, parent_item):
		QGraphicsItem.__init__(self, parent_item)
		self.radar_contact = parent_item.radar_contact
		self.info_text = ''
		self.rectangle = QRectF()
		self.setCursor(Qt.PointingHandCursor)
		self.setPos(TextBoxItem.init_offset)
		self.mouse_hovering = False
		self.paint_border = True
		self.setFlag(QGraphicsItem.ItemIsMovable, True)
		self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
		self.setAcceptHoverEvents(True)
		self.updateContents()
	
	def updateContents(self):
		self.prepareGeometryChange()
		expand = self.mouse_hovering or self.radar_contact is selection.acft or env.linkedStrip(self.radar_contact) != None
		self.paint_border = expand
		self.info_text = infoTextLines(self.radar_contact, not expand)
		self.rectangle = TextBoxItem.txt_rect_3lines if expand else TextBoxItem.txt_rect_2lines
	
	def positionQuadrant(self):
		return (1 if self.pos().x() > 0 else -1), (1 if self.pos().y() > 0 else -1)
	
	def calloutConnectingPoint(self):
		q = self.positionQuadrant()
		if q == (-1, -1): return self.rectangle.bottomRight()
		elif q == (-1, 1): return self.rectangle.topRight()
		elif q == (1, -1): return self.rectangle.bottomLeft()
		elif q == (1, 1): return self.rectangle.topLeft()
	
	def paint(self, painter, option, widget):
		coloured_pen = new_pen(ACFT_pen_colour(self.radar_contact))
		# 1. Write info text
		painter.setPen(coloured_pen)
		painter.drawText(self.rectangle, Qt.AlignLeft | Qt.AlignVCenter, self.info_text)
		# 2. Draw container box?
		if self.paint_border:
			pen = coloured_pen if self.radar_contact is selection.acft else new_pen(settings.colour('radar_tag_line'))
			if self.radar_contact.individual_cheat:
				pen.setStyle(Qt.DashLine)
			painter.setPen(pen)
			painter.drawRect(self.rectangle)
		
	def boundingRect(self):
		return self.rectangle
	

	# EVENTS
	
	def itemChange(self, change, value):
		if change == QGraphicsItem.ItemPositionChange:
			self.parentItem().textBoxChanged()
		return QGraphicsItem.itemChange(self, change, value)
	
	def hoverEnterEvent(self, event):
		self.mouse_hovering = True
		self.updateContents()
		self.parentItem().textBoxChanged()
		QGraphicsItem.hoverEnterEvent(self, event)
	
	def hoverLeaveEvent(self, event):
		self.mouse_hovering = False
		self.updateContents()
		self.parentItem().textBoxChanged()
		QGraphicsItem.hoverLeaveEvent(self, event)

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			selection.selectAircraft(self.radar_contact)
		elif event.button() == Qt.MiddleButton:
			if event.modifiers() & Qt.ShiftModifier:
				selection.unlinkAircraft(self.radar_contact)
			else:
				selection.linkAircraft(self.radar_contact)
			event.accept()
		QGraphicsItem.mousePressEvent(self, event)

	def mouseDoubleClickEvent(self, event):
		if event.button() == Qt.LeftButton:
			if event.modifiers() & Qt.ShiftModifier: # reset box position
				self.setPos(TextBoxItem.init_offset)
				self.parentItem().textBoxChanged()
			else:
				strip = selection.strip
				if strip != None:
					signals.stripEditRequest.emit(strip)
			event.accept()
		else:
			QGraphicsItem.mouseDoubleClickEvent(self, event)
