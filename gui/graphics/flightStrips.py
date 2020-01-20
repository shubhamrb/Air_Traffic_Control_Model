from datetime import timedelta

from PyQt5.QtCore import Qt, QRect, QRectF, QSize
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsPixmapItem, QStyleOptionGraphicsItem
from PyQt5.QtGui import QTextDocument, QPen, QBrush, QDrag, QPixmap, QPainter, QFontMetrics

from session.config import settings
from session.env import env

from data.util import some
from data.fpl import FPL
from data.nav import world_navpoint_db, NavpointError
from data.params import time_to_fly
from data.strip import strip_mime_type, received_from_detail, sent_to_detail, assigned_SQ_detail, \
		parsed_route_detail, soft_link_detail, recycled_detail, auto_printed_detail, duplicate_callsign_detail

from gui.actions import new_strip_dialog
from gui.misc import signals, selection
from gui.graphics.miscGraphics import new_pen, EmptyGraphicsItem

from models.cpdlc import ConnectionStatus


# ---------- Constants ----------

strip_IFR_border_width = 3
strip_text_bottom_margin = 6
strip_text_max_rect = QRect(0, 0, 500, 100)
loose_strip_width = 200
loose_strip_height = 52 # FIXME depend on text height
loose_strip_margin = 2 # between selection indicator and strip border
spacing_hint_threshold = timedelta(minutes=30) # threshold above which not to display (useless) hint
spacing_hint_speed_var_thr = 5 # kt (minimum speed difference between the two aircraft to show a variability)

# -------------------------------



def acknowledge_strip(strip):
	strip.writeDetail(received_from_detail, None)
	strip.writeDetail(sent_to_detail, None)
	strip.writeDetail(recycled_detail, None)
	strip.writeDetail(auto_printed_detail, None)


def strip_mouse_press(strip, event):
	if event.button() == Qt.LeftButton:
		acknowledge_strip(strip)
		selection.selectStrip(strip)
	elif event.button() == Qt.MiddleButton:
		if event.modifiers() & Qt.ShiftModifier: # STRIP UNLINK  REQUEST
			if strip is selection.strip:
				if selection.fpl != None and selection.acft != None: # both are linked
					signals.statusBarMsg.emit('Ambiguous action. Use SHIFT+MMB on FPL or radar contact to unlink.')
				elif selection.fpl == None and selection.acft != None: # XPDR link only
					strip.linkAircraft(None)
					signals.stripInfoChanged.emit()
					selection.selectAircraft(selection.acft)
				elif selection.fpl != None and selection.acft == None: # FPL link only
					strip.linkFPL(None)
					signals.stripInfoChanged.emit()
					selection.selectFPL(selection.fpl)
		else: # STRIP LINK REQUEST
			if selection.fpl != None and env.linkedStrip(selection.fpl) == None and strip.linkedFPL() == None:
				strip.linkFPL(selection.fpl)
				signals.stripInfoChanged.emit()
				selection.selectStrip(strip)
			elif selection.acft != None and env.linkedStrip(selection.acft) == None and strip.linkedAircraft() == None:
				strip.linkAircraft(selection.acft)
				if settings.strip_autofill_on_ACFT_link:
					strip.fillFromXPDR()
				signals.stripInfoChanged.emit()
				selection.selectStrip(strip)
			if strip is selection.strip:
				acknowledge_strip(strip)




def spacing_hint(strip, prev_strip):
	acft = strip.linkedAircraft()
	if acft == None or acft.considerOnGround():
		return None
	try:
		dest = world_navpoint_db.findAirfield(strip.lookup(FPL.ICAO_ARR, fpl=True))
	except (NavpointError, ValueError):
		return None
	speed = acft.groundSpeed()
	if speed != None and prev_strip.lookup(FPL.ICAO_ARR, fpl=True) == dest.code:
		prev_acft = prev_strip.linkedAircraft()
		if prev_acft != None and not prev_acft.considerOnGround(): # ACFT and previous are both identified and inbound
			prev_speed = prev_acft.groundSpeed()
			if prev_speed != None:
				dist_to_prev = acft.coords().distanceTo(prev_acft.coords())
				prev_to_dest = prev_acft.coords().distanceTo(dest.coordinates)
				try:
					my_ttf = time_to_fly(dist_to_prev, speed) + time_to_fly(prev_to_dest, speed)
					their_ttf = time_to_fly(prev_to_dest, prev_speed)
					td_diff = my_ttf - their_ttf
					if td_diff >= spacing_hint_threshold:
						return None
				except ValueError:
					pass
				else: # return a spacing hint
					diff_seconds = int(td_diff.total_seconds())
					if diff_seconds < 0:
						hint = '-%d:%02d' % (-diff_seconds // 60, -diff_seconds % 60)
					else:
						hint = '%d:%02d' % (diff_seconds // 60, diff_seconds % 60)
					diff_speed = speed.diff(prev_speed, tolerance=spacing_hint_speed_var_thr)
					if diff_speed != 0:
						hint += '&darr;' if diff_speed < 0 else '&uarr;'
					if diff_seconds < 0:
						hint += ' !!overtake'
					return '[%s]' % hint
	return None




def strip_size_hint(text_font):
	txt_rect = QFontMetrics(text_font).boundingRect(strip_text_max_rect, Qt.AlignLeft, '##\n##\n##')
	return QSize(220, txt_rect.height() + strip_IFR_border_width + strip_text_bottom_margin)



def paint_strip_box(parent_widget, painter, strip, rect):
	acft = strip.linkedAircraft()
	
	### LINE 1
	scs = strip.callsign(fpl=True)
	acs = None if acft == None else acft.xpdrCallsign()
	cs = some(scs, acs)
	if settings.strip_CPDLC_integration and cs != None and (acs == None or acs == scs):
		sdl = env.cpdlc.currentDataLink(cs)
	else:
		sdl = None
	## Decorated callsign section
	callsign_section = ''
	# handover from
	fromATC = strip.lookup(received_from_detail)
	if fromATC != None:
		callsign_section += fromATC + ' &gt;&gt; '
	# callsign(s)
	if sdl != None:
		callsign_section += '⚡ ' if sdl.status() == ConnectionStatus.OK else '[⚡] '
	callsign_section += '<strong>%s</strong>' % some(cs, '?')
	if scs != None and acs != None and scs != acs: # callsign conflict with XPDR
		callsign_section += ' <strong>(%s)</strong>' % acs
	if strip.lookup(FPL.COMMENTS) != None:
		callsign_section += '*'
	# handover to
	toATC = strip.lookup(sent_to_detail)
	if toATC != None:
		callsign_section += ' &gt;&gt; ' + toATC
	if strip.lookup(duplicate_callsign_detail): # duplicate callsign warning
		callsign_section += ' !!dup'
	line1_sections = [callsign_section]
	## Wake turb. cat. / aircraft type
	atyp = None if acft == None else acft.xpdrAcftType()
	typesec = some(strip.lookup(FPL.ACFT_TYPE, fpl=True), some(atyp, ''))
	wtc = strip.lookup(FPL.WTC, fpl=True)
	if wtc != None:
		typesec += '/%s' % wtc
	line1_sections.append(typesec)
	## Optional sections
	# transponder code
	assSQ = strip.lookup(assigned_SQ_detail)
	if assSQ != None:
		if acft == None: # no ACFT linked
			line1_sections.append('sq=%04o' % assSQ)
		else:
			sq = acft.xpdrCode()
			if sq != None and sq != assSQ:
				line1_sections.append('sq=%04o (%04o)' % (assSQ, sq))
	# conflicts
	conflicts = []
	alert_lvl_hi = alert_lvl_lo = False
	if strip.transponderConflictList() != []:
		conflicts.append('!!XPDR')
		alert_lvl_hi = True
	if sdl != None and sdl.status() != ConnectionStatus.OK:
		conflicts.append('!!CPDLC')
		if sdl.status() == ConnectionStatus.PROBLEM:
			alert_lvl_hi = True
		else:
			alert_lvl_lo = True
	if settings.strip_route_vect_warnings:
		if len(strip.vectoringConflicts(env.QNH())) != 0:
			conflicts.append('!!vect')
			alert_lvl_lo = True
		elif strip.routeConflict():
			conflicts.append('!!route')
			alert_lvl_lo = True
	if len(conflicts) > 0:
		line1_sections.append(' '.join(conflicts))
	
	### LINE 2
	line2_sections = []
	if settings.APP_spacing_hints:
		prev = env.strips.previousInSequence(strip)
		if prev != None:
			hint = spacing_hint(strip, prev)
			if hint != None:
				line2_sections.append('%s&nbsp;' % hint)
	parsed_route = strip.lookup(parsed_route_detail)
	if parsed_route == None:
		arr = strip.lookup(FPL.ICAO_ARR, fpl=True)
		if arr != None:
			line2_sections.append(arr)
	elif acft == None:
		line2_sections.append(str(parsed_route))
	else:
		line2_sections.append(parsed_route.toGoStr(acft.coords()))
	
	## MAKE DOCUMENT
	html_line1 = ' &nbsp; '.join(line1_sections)
	html_line2 = ' '.join(line2_sections)
	doc = QTextDocument(parent_widget)
	doc.setHtml('<html><body><p>%s<br>&nbsp;&nbsp; %s</p></body></html>' % (html_line1, html_line2))
	
	## PAINT
	painter.save()
	## Background and borders
	if acft == None:
		if strip.lookup(soft_link_detail) == None:
			bgcol = 'strip_unlinked'
		else:
			bgcol = 'strip_unlinked_identified'
	else: # an aircraft is linked
		if alert_lvl_hi:
			bgcol = 'strip_linked_alert'
		elif alert_lvl_lo:
			bgcol = 'strip_linked_warning'
		else:
			bgcol = 'strip_linked_OK'
	if strip is selection.strip:
		painter.setPen(new_pen(Qt.black, width=2))
	else:
		painter.setPen(new_pen(Qt.darkGray))
	painter.setBrush(QBrush(settings.colour(bgcol)))
	painter.drawRect(rect)
	painter.translate(rect.topLeft())
	rules = strip.lookup(FPL.FLIGHT_RULES, fpl=True)
	if rules != None: # add a border along bottom edge of strip
		painter.setPen(Qt.NoPen)
		painter.setBrush(QBrush(Qt.black, style={'IFR': Qt.SolidPattern, 'VFR': Qt.BDiagPattern}.get(rules, Qt.NoBrush)))
		painter.drawRect(0, rect.height() - strip_IFR_border_width, rect.width(), strip_IFR_border_width)
	## Text contents
	doc.drawContents(painter, QRectF(0, 0, rect.width(), rect.height() - strip_IFR_border_width))
	painter.restore()








class LooseStripItem(QGraphicsItem):
	def __init__(self, strip, compact, parent=None):
		QGraphicsItem.__init__(self, parent)
		self.setFlag(QGraphicsItem.ItemIsMovable, True)
		self.strip = strip
		self.compact_display = compact
	
	def setCompact(self, toggle):
		self.compact_display = toggle
		self.prepareGeometryChange()
	
	def boundingRect(self):
		w = loose_strip_width
		h = loose_strip_height
		if self.compact_display:
			w /= 2
			h /= 2
		return QRectF(-w / 2, -h / 2, w, h)
	
	def paint(self, painter, option, widget):
		if self.strip is selection.strip:
			painter.save()
			painter.setPen(new_pen(settings.colour('selection_indicator'), width=2))
			painter.drawRect(self.boundingRect())
			painter.restore()
		painter.save()
		painter.translate(option.rect.topLeft())
		painter.translate(loose_strip_margin, loose_strip_margin)
		doc_rect = QRectF(0, 0, option.rect.width() - 2 * loose_strip_margin, option.rect.height() - 2 * loose_strip_margin)
		paint_strip_box(widget, painter, self.strip, doc_rect)
		painter.restore()
	
	def toPixmap(self):
		rect = self.boundingRect()
		pixmap = QPixmap(rect.width(), rect.height())
		pixmap.fill(Qt.darkRed)
		painter = QPainter(pixmap)
		painter.drawRect(rect)
		self.scene().render(painter, QRectF(), self.sceneBoundingRect())
		painter.end()
		return pixmap
	
	def mousePressEvent(self, event):
		self._pos_at_mouse_press = self.pos()
		strip_mouse_press(self.strip, event)
		QGraphicsItem.mousePressEvent(self, event)
		
	def mouseMoveEvent(self, event):
		if event.modifiers() & Qt.ShiftModifier:
			QGraphicsItem.mouseMoveEvent(self, event)
		else:
			drag = QDrag(event.widget())
			drag.setMimeData(env.strips.mkMimeDez(self.strip))
			pixmap = self.toPixmap()
			drag.setPixmap(pixmap)
			drag.setHotSpot(pixmap.rect().center())
			self.setVisible(False)
			if drag.exec() != Qt.MoveAction:
				self.setVisible(True)
			#if drag_result == Qt.IgnoreAction: # no drop action performed; must restore strip
			#	self.setPos(self._pos_at_mouse_press)

	def mouseDoubleClickEvent(self, event):
		signals.stripEditRequest.emit(self.strip)
		event.accept()
		QGraphicsItem.mouseDoubleClickEvent(self, event)








class LooseStripBayScene(QGraphicsScene):
	def __init__(self, parent):
		QGraphicsScene.__init__(self, parent)
		self.gui = parent
		self.bg_item = None
		self.compact_strips = False
		self.fillBackground()
		wref = 5 * loose_strip_width
		href = .75 * wref
		self.addRect(QRectF(-wref/2, -href/2, wref, href), pen=QPen(Qt.NoPen)) # avoid empty scene
		self.strip_items = EmptyGraphicsItem()
		self.addItem(self.strip_items)
		self.strip_items.setZValue(1) # gets strips on top of bg_item
		# External signal connections below. CAUTION: these must all be disconnected on widget deletion
		signals.selectionChanged.connect(self.updateSelection)
		signals.colourConfigReloaded.connect(self.fillBackground)
		env.strips.stripMoved.connect(self.removeInvisibleStripItems)
	
	def disconnectAllSignals(self):
		signals.selectionChanged.disconnect(self.updateSelection)
		signals.colourConfigReloaded.disconnect(self.fillBackground)
		env.strips.stripMoved.disconnect(self.removeInvisibleStripItems)
	
	def getStrips(self):
		return [item.strip for item in self.strip_items.childItems()]
	
	def fillBackground(self):
		self.setBackgroundBrush(settings.colour('loose_strip_bay_background'))
	
	def clearBgImg(self):
		if self.bg_item != None:
			self.removeItem(self.bg_item)
			self.bg_item = None
	
	def setBgImg(self, pixmap, scale): # pixmap None to clear background
		self.clearBgImg()
		self.bg_item = QGraphicsPixmapItem(pixmap, None)
		rect = self.bg_item.boundingRect()
		self.bg_item.setScale(scale * loose_strip_width / rect.width())
		self.bg_item.setOffset(-rect.center())
		self.addItem(self.bg_item)
	
	def setCompactStrips(self, b):
		self.compact_strips = b
		for item in self.strip_items.childItems():
			item.setCompact(b)
	
	def updateSelection(self):
		for item in self.strip_items.childItems():
			item.setZValue(1 if item.strip is selection.strip else 0)
			item.update()
	
	def placeNewStripItem(self, strip, pos):
		item = LooseStripItem(strip, self.compact_strips)
		item.setPos(pos)
		self.addStripItem(item)
	
	def deleteStripItem(self, strip):
		self.removeItem(next(item for item in self.strip_items.childItems() if item.strip is strip))
	
	def removeInvisibleStripItems(self, strip):
		for item in self.strip_items.childItems():
			if not item.isVisible():
				self.removeItem(item)
	
	def deleteAllStripItems(self):
		for item in self.strip_items.childItems():
			self.removeItem(item)
	
	def addStripItem(self, item):
		item.setParentItem(self.strip_items)
	
	def dropEvent(self, event):
		if event.mimeData().hasFormat(strip_mime_type):
			strip = env.strips.fromMimeDez(event.mimeData())
			try: # maybe it was already inside this bay
				item = next(item for item in self.strip_items.childItems() if item.strip is strip)
				item.setPos(event.scenePos())
				item.setVisible(True)
			except StopIteration:
				env.strips.repositionStrip(strip, None)
				self.placeNewStripItem(strip, event.scenePos())
			signals.selectionChanged.emit()
			event.acceptProposedAction()
	
	def mousePressEvent(self, event):
		if self.mouseGrabberItem() == None:
			selection.deselect()
			event.accept()
		QGraphicsScene.mousePressEvent(self, event)
	
	def mouseDoubleClickEvent(self, event):
		QGraphicsScene.mouseDoubleClickEvent(self, event)
		if not event.isAccepted(): # avoid creating when double clicking on a strip item
			event.accept()
			strip = new_strip_dialog(self.gui, None)
			if strip != None:
				self.placeNewStripItem(strip, event.scenePos())
				selection.selectStrip(strip)
	
	def dragMoveEvent(self, event):
		pass # Scene's default impl. ignores the event when no item is under mouse (this enables mouse drop on scene)

