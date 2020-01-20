from datetime import timedelta

from PyQt5.QtCore import Qt, pyqtSignal, QRectF, \
			QItemSelectionModel, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import QTableView, QTabWidget, QAbstractItemView, QStyle, \
			QStyledItemDelegate, QTabBar, QHeaderView, QGraphicsView
from PyQt5.QtGui import QIcon, QPen, QBrush, QFont, QColor

from session.config import settings
from session.env import env

from data.utc import duration_str
from data.strip import Strip, strip_mime_type, received_from_detail, recycled_detail, \
			auto_printed_detail, runway_box_detail, rack_detail, soft_link_detail

from gui.misc import signals, selection, IconFile
from gui.actions import new_strip_dialog
from gui.graphics.flightStrips import strip_size_hint, strip_mouse_press, paint_strip_box
from gui.graphics.miscGraphics import new_pen, coloured_square_icon
from gui.dialog.miscDialogs import EditRackDialog


# ---------- Constants ----------

strip_placeholder_margin = 5 # for delegate text document and deco
strip_icon_max_width = 20
max_WTC_time_disp = timedelta(minutes=5)

# -------------------------------



class StripItemDelegate(QStyledItemDelegate):
	def __init__(self, parent):
		QStyledItemDelegate.__init__(self, parent)
		self.show_icons = True
	
	def setShowIcons(self, b):
		self.show_icons = b
	
	def sizeHint(self, option, index): # QStyleOptionViewItem option, QModelIndex index
		return strip_size_hint(option.font)
	
	def paint(self, painter, option, index):
		strip = index.model().stripAt(index)
		# STYLE: rely ONLY on models' data to avoid redefining "stripAt"
		# for every model, e.g. here: strip = env.strips.stripAt(index.data())
		icon = None
		if self.show_icons and strip != None:
			if strip.lookup(recycled_detail):
				icon = QIcon(IconFile.pixmap_strip_recycled)
			elif strip.lookup(received_from_detail) != None:
				icon = QIcon(IconFile.pixmap_strip_received)
			elif strip.lookup(auto_printed_detail) != None:
				icon = QIcon(IconFile.pixmap_strip_printed)
		smw = option.rect.width() # width of strip with margins
		m2 = 2 * strip_placeholder_margin
		h = option.rect.height()
		painter.save()
		painter.translate(option.rect.topLeft())
		if icon == None:
			iw = 0
		else:
			iw = min(strip_icon_max_width, h - m2) # icon width
			smw -= iw + strip_placeholder_margin
			icon.paint(painter, 0, (h - iw) / 2, iw, iw)
		if strip != None:
			strip_rect = QRectF(strip_placeholder_margin + iw, strip_placeholder_margin, smw - m2, h - m2)
			paint_strip_box(self, painter, strip, strip_rect)
		painter.restore()





class RackedStripsFilterModel(QSortFilterProxyModel):
	def __init__(self, parent):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(env.strips)
		self.rack_filter_list = [] # WARNING: should keep source model rack order (this is just a filter model)
	
	def setRackFilter(self, racks):
		self.rack_filter_list = [r for r in env.strips.rackNames() if r in racks] # keep source order
		self.invalidateFilter()
	
	def updateRackFilter(self, renamed_racks):
		self.setRackFilter([renamed_racks.get(r, r) for r in self.rack_filter_list]) # this also removes those no more existing
	
	def rackName(self, proxy_column):
		return self.rack_filter_list[proxy_column]
	
	def stripAt(self, proxy_index):
		return self.sourceModel().stripAt(self.mapToSource(proxy_index))
	
	def stripModelIndex(self, strip):
		smi = self.sourceModel().stripModelIndex(strip)
		return None if smi == None else self.mapFromSource(smi)

	## MODEL STUFF
	def filterAcceptsColumn(self, sourceCol, sourceParent):
		return self.sourceModel().rackName(sourceCol) in self.rack_filter_list
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		check_src_indexes = [si for si, sr in enumerate(self.sourceModel().rackNames()) if sr in self.rack_filter_list]
		if check_src_indexes == []:
			return False
		else:
			return sourceRow < max(self.sourceModel().rackLength(i) for i in check_src_indexes)
	
	def dropMimeData(self, mime, drop_action, row, column, parent):
		if not parent.isValid() and 0 <= column < len(self.rack_filter_list): # capture dropping under last strip
			src_rack_index = self.sourceModel().rackIndex(self.rackName(column))
			return self.sourceModel().dropMimeData(mime, drop_action, row, src_rack_index, parent)
		return QSortFilterProxyModel.dropMimeData(self, mime, drop_action, row, column, parent)









class StripTableView(QTableView):
	'''
	CAUTION: this is derived for *ANY* table view with draggable strips,
	incl. rack tables, tabbed racks, and even RWY boxes
	'''
	def __init__(self, parent):
		QTableView.__init__(self, parent)
		self.horizontalHeader().setSectionsMovable(True)
		self.setItemDelegate(StripItemDelegate(self))
		self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
		self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
		self.setSelectionMode(QAbstractItemView.SingleSelection)
		self.setDragEnabled(True)
		self.setAcceptDrops(True)
		self.setShowGrid(False)
		self.horizontalHeader().sectionDoubleClicked.connect(self.columnDoubleClicked)
	
	def setDivideHorizWidth(self, toggle):
		for section in range(self.horizontalHeader().count()):
			self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch if toggle else QHeaderView.Interactive)
	
	def updateSelection(self):
		self.clearSelection()
		if selection.strip != None:
			mi = self.model().stripModelIndex(selection.strip)
			if mi != None:
				self.selectionModel().select(mi, QItemSelectionModel.ClearAndSelect)
				self.scrollTo(mi)
	
	def mousePressEvent(self, event):
		QTableView.mousePressEvent(self, event)
		index = self.indexAt(event.pos())
		strip = self.model().stripAt(index) if index.isValid() else None
		if strip == None:
			selection.deselect()
		else:
			strip_mouse_press(strip, event)
			signals.selectionChanged.emit() # resync selection if event did not change it
	
	def dropEvent(self, event):
		QTableView.dropEvent(self, event)
		if not event.isAccepted(): # happens when outside of table area
			column = self.horizontalHeader().logicalIndexAt(event.pos())
			row = self.verticalHeader().logicalIndexAt(event.pos())
			if self.model().dropMimeData(event.mimeData(), event.dropAction(), row, column, QModelIndex()):
				event.acceptProposedAction()
		if event.isAccepted():
			signals.selectionChanged.emit()
	
	def mouseDoubleClickEvent(self, event):
		strip = selection.strip
		if event.button() == Qt.LeftButton and strip != None: # double-clicked on a strip
			event.accept()
			if event.modifiers() & Qt.ShiftModifier: # indicate radar link or identification
				acft = strip.linkedAircraft()
				if acft == None:
					acft = strip.lookup(soft_link_detail)
				if acft != None:
					signals.indicatePoint.emit(acft.coords())
			else: # request strip edit
				signals.stripEditRequest.emit(strip)
		else: # double-clicked off strip
			self.doubleClickOffStrip(event)
		if not event.isAccepted():
			QTableView.mouseDoubleClickEvent(self, event)
	
	def columnDoubleClicked(self, column):
		if column != -1:
			EditRackDialog(self, self.model().rackName(column)).exec()
	
	def doubleClickOffStrip(self, event):
		column = self.horizontalHeader().logicalIndexAt(event.pos())
		if column != -1 and not event.modifiers() & Qt.ShiftModifier:
			rack = self.model().rackName(column)
			new_strip_dialog(self, rack)
			event.accept()








	
	


###############################

##        TABBED VIEW        ##

###############################



class StripRackTabs(QTabWidget):
	def __init__(self, parent=None):
		QTabWidget.__init__(self, parent)
		self.tab_bar = StripRackTabBar(self)
		self.setTabBar(self.tab_bar)
		self.updateTabIcons()
	
	def rackTabs(self):
		'''
		Enumerates the tabbed rack view widgets.
		'''
		return [self.widget(i) for i in range(self.count())]
	
	def setTabs(self, racks):
		for index, rack in enumerate(racks):
			try:
				i = next(i for i in range(self.count()) if self.widget(i).singleRackFilter() == rack)
				if i > index:
					self.tabBar().moveTab(i, index)
			except StopIteration: # must insert view here
				self.insertTab(index, SingleRackColumnView(self, rack), rack)
		n = len(racks)
		while self.count() > n:
			w = self.widget(n)
			self.removeTab(n)
			w.deleteLater()
	
	def updateTabName(self, old_name, new_name):
		for i, w in enumerate(self.rackTabs()):
			if w.singleRackFilter() == old_name: # replace tab
				self.removeTab(i)
				w.deleteLater()
				self.insertTab(i, SingleRackColumnView(self, new_name), new_name)
				self.setCurrentIndex(i)
				break
	
	def updateTabIcons(self):
		for i, w in enumerate(self.rackTabs()):
			try:
				self.setTabIcon(i, coloured_square_icon(settings.rack_colours[w.singleRackFilter()], width=12))
			except KeyError:
				self.setTabIcon(i, QIcon())
	
	def updateSelection(self):
		for i in range(self.count()):
			self.widget(i).updateSelection()
		strip = selection.strip
		if strip != None and strip.lookup(runway_box_detail) == None: # strip is racked or loose
			for w in self.rackTabs():
				if w.singleRackFilter() == strip.lookup(rack_detail):
					self.setCurrentWidget(w)
					break




class StripRackTabBar(QTabBar):
	def __init__(self, parent=None):
		QTabBar.__init__(self, parent)
		self.setAcceptDrops(True)
		# self.setChangeCurrentOnDrag(True) # FUTURE insert? when Qt>=5.4
	
	def dragEnterEvent(self, event): # FUTURE Useless if self.changeCurrentOnDrag()
		if event.mimeData().hasFormat(strip_mime_type):
			event.acceptProposedAction()
	
	def dragMoveEvent(self, event): # FUTURE Useless if self.changeCurrentOnDrag()
		itab = self.tabAt(event.pos())
		if itab != -1:
			self.setCurrentIndex(itab)
	
	def dropEvent(self, event):
		if event.mimeData().hasFormat(strip_mime_type):
			itab = self.currentIndex()
			strip = env.strips.fromMimeDez(event.mimeData())
			rack = self.parentWidget().widget(itab).singleRackFilter()
			env.strips.repositionStrip(strip, rack)
			event.acceptProposedAction()
			signals.selectionChanged.emit()
	
	def mouseDoubleClickEvent(self, event):
		itab = self.tabAt(event.pos())
		if itab != -1:
			rack = self.parentWidget().widget(itab).singleRackFilter()
			EditRackDialog(self, rack).exec()
			event.accept()
		else:
			QTabBar.mouseDoubleClickEvent(self, event)




class SingleRackColumnView(StripTableView):
	def __init__(self, parent, single_rack_filter):
		StripTableView.__init__(self, parent)
		self.table_model = RackedStripsFilterModel(self)
		self.setModel(self.table_model)
		self.single_rack_filter = single_rack_filter # assigned below
		self.table_model.setRackFilter([single_rack_filter])
		self.horizontalHeader().setStretchLastSection(True)
		self.horizontalHeader().setVisible(False)
	
	def singleRackFilter(self):
		return self.single_rack_filter











##############################

##       RUNWAY BOXES       ##

##############################



class RunwayBoxItemDelegate(QStyledItemDelegate):
	def __init__(self, parent):
		QStyledItemDelegate.__init__(self, parent)
	
	def sizeHint(self, option, index):
		return strip_size_hint(option.font)
	
	def paint(self, painter, option, index):
		strip = index.model().stripAt(index)
		# STYLE: rely ONLY on models' data to avoid needing stripAt redef for every model
		# e.g. here: strip = env.strips.stripAt(index.data())
		physical_RWY_index = index.model().boxAt(index)
		rwy_txt = env.airport_data.physicalRunwayNameFromUse(physical_RWY_index)
		m2 = 2 * strip_placeholder_margin
		painter.save()
		painter.translate(option.rect.topLeft())
		box = QRectF(strip_placeholder_margin, strip_placeholder_margin, option.rect.width() - m2, option.rect.height() - m2)
		vertical_sep = box.height() * .6
		if strip == None:
			timer, wtc = env.airport_data.physicalRunwayWtcTimer(physical_RWY_index)
			if timer > max_WTC_time_disp:
				timer_txt = ''
			else:
				timer_txt = duration_str(timer)
				if wtc != None:
					timer_txt += ' / %s' % wtc
			painter.setPen(QPen(Qt.NoPen))
			painter.setBrush(QBrush(QColor('#EEEEEE')))
			painter.drawRect(box)
			painter.setPen(new_pen(Qt.black))
			painter.drawText(box.adjusted(0, vertical_sep, 0, 0), Qt.AlignCenter, timer_txt) # Normal font
			font = QFont(painter.font())
			font.setPointSize(font.pointSize() + 3)
			painter.setFont(font)
			painter.drawText(box.adjusted(0, 0, 0, -vertical_sep), Qt.AlignCenter, rwy_txt)
		else:
			paint_strip_box(self, painter, strip, box)
			txt_box = box.adjusted(box.width() - 50, vertical_sep, 0, 0)
			painter.setPen(QPen(Qt.NoPen))
			painter.setBrush(QBrush(QColor('#EEEEEE')))
			painter.drawRect(txt_box)
			painter.setPen(new_pen(Qt.black))
			painter.drawText(txt_box, Qt.AlignCenter, rwy_txt)
		painter.restore()





class RunwayBoxTableModel(QAbstractTableModel):
	def __init__(self, parent):
		QAbstractTableModel.__init__(self, parent)
		self.box_count = 0 if env.airport_data == None else env.airport_data.physicalRunwayCount()
		self.vertical = False

	def rowCount(self, parent=QModelIndex()):
		if parent.isValid():
			return 0
		return self.box_count if self.vertical else 1

	def columnCount(self, parent=QModelIndex()):
		if parent.isValid():
			return 0
		return 1 if self.vertical else self.box_count
	
	def data(self, index, role):
		strip = self.stripAt(index)
		if role == Qt.DisplayRole:
			return str(strip) if strip != None else 'Physical RWY %s' % self.boxAt(index)
	
	def flags(self, index):
		flags = Qt.ItemIsEnabled
		if index.isValid():
			if self.stripAt(index) == None:
				flags |= Qt.ItemIsDropEnabled
			else:
				flags |= Qt.ItemIsDragEnabled | Qt.ItemIsSelectable
		return flags

	## DRAG AND DROP STUFF
	def supportedDragActions(self):
		return Qt.MoveAction
	
	def supportedDropActions(self):
		return Qt.MoveAction
	
	def mimeTypes(self):
		return [strip_mime_type]
	
	def mimeData(self, indices):
		assert len(indices) == 1
		return env.strips.mkMimeDez(self.stripAt(indices[0]))
	
	def dropMimeData(self, mime, drop_action, row, column, parent):
		if parent.isValid() and drop_action == Qt.MoveAction and mime.hasFormat(strip_mime_type):
			drop_rwy = self.boxAt(parent)
			dropped_strip = env.strips.fromMimeDez(mime)
			was_in_box = dropped_strip.lookup(runway_box_detail)
			if was_in_box != None:
				mi1 = self.boxModelIndex(was_in_box)
				self.dataChanged.emit(mi1, mi1)
			env.strips.repositionStrip(dropped_strip, None, box=drop_rwy)
			mi2 = self.boxModelIndex(drop_rwy)
			self.dataChanged.emit(mi2, mi2)
			return True
		return False

	## ACCESSORS
	def boxAt(self, index):
		return index.row() if self.vertical else index.column()
	
	def boxModelIndex(self, section):
		return self.index(section, 0) if self.vertical else self.index(0, section)
	
	def stripAt(self, index):
		try:
			return env.strips.findStrip(lambda strip: strip.lookup(runway_box_detail) == self.boxAt(index))
		except StopIteration:
			return None
	
	def stripModelIndex(self, strip):
		rwy = strip.lookup(runway_box_detail)
		return None if rwy == None else self.boxModelIndex(rwy)

	## MODIFIERS
	def setVertical(self, toggle):
		self.beginResetModel()
		self.vertical = toggle
		self.endResetModel()
	
	def updateVisibleWtcTimers(self):
		for i in range(self.box_count):
			mi = self.boxModelIndex(i)
			if self.stripAt(mi) == None:
				self.dataChanged.emit(mi, mi)




class RunwayBoxFilterModel(QSortFilterProxyModel):
	def __init__(self, parent, source_model):
		QSortFilterProxyModel.__init__(self, parent)
		self.setSourceModel(source_model)
	
	def boxAt(self, model_index):
		return self.sourceModel().boxAt(self.mapToSource(model_index))
	
	def stripAt(self, model_index):
		return self.sourceModel().stripAt(self.mapToSource(model_index))
	
	def stripModelIndex(self, strip):
		smi = self.sourceModel().stripModelIndex(strip)
		return None if smi == None else self.mapFromSource(smi)

	## FILTERING	
	def acceptPhysicalRunway(self, phyrwy):
		rwy1, rwy2 = env.airport_data.physicalRunway(phyrwy)
		return rwy1.inUse() or rwy2.inUse()

	## MODEL STUFF
	def filterAcceptsColumn(self, sourceCol, sourceParent):
		return self.sourceModel().vertical or self.acceptPhysicalRunway(sourceCol) \
			or self.sourceModel().stripAt(self.sourceModel().boxModelIndex(sourceCol)) != None
	
	def filterAcceptsRow(self, sourceRow, sourceParent):
		return not self.sourceModel().vertical or self.acceptPhysicalRunway(sourceRow) \
			or self.sourceModel().stripAt(self.sourceModel().boxModelIndex(sourceRow)) != None



class RunwayBoxesView(StripTableView):
	def __init__(self, parent=None):
		StripTableView.__init__(self, parent)
		self.full_model = RunwayBoxTableModel(self)
		self.filter_model = RunwayBoxFilterModel(self, self.full_model)
		self.setShowGrid(True)
		self.horizontalHeader().setVisible(False)
		self.verticalHeader().setVisible(False)
		self.setItemDelegate(RunwayBoxItemDelegate(self))
		self.setDivideHorizWidth(True)
		if env.airport_data == None:
			self.setEnabled(False)
		else:
			self.setModel(self.filter_model)
			env.strips.rwyBoxFreed.connect(self.refilter)
			signals.selectionChanged.connect(self.updateSelection) # self.updateSelection is inherited from StripTableView
			signals.runwayUseChanged.connect(self.refilter)
			signals.fastClockTick.connect(self.full_model.updateVisibleWtcTimers)
	
	def refilter(self):
		self.filter_model.invalidateFilter()
		self.setDivideHorizWidth(True)
	
	def setVerticalLayout(self, toggle):
		self.full_model.setVertical(toggle)
	
	def doubleClickOffStrip(self, event):
		pass


