from data.util import some
from data.utc import now, rel_datetime_str


# ---------- Constants ----------

# -------------------------------


# CALLSIGN      str
# ACFT_TYPE     str
# WTC           str
# ICAO_DEP      str
# ICAO_ARR      str
# ICAO_ALT      str
# CRUISE_ALT    str
# TAS           Speed
# SOULS         int
# TIME_OF_DEP   datetime
# EET           timedelta
# FLIGHT_RULES  str
# ROUTE         str
# COMMENTS      str




class FplError(Exception):
	pass







class FPL:
	# STATIC stuff
	statuses = FILED, OPEN, CLOSED = range(3)
	details = CALLSIGN, ACFT_TYPE, WTC, ICAO_DEP, ICAO_ARR, ICAO_ALT, \
		CRUISE_ALT, TAS, SOULS, TIME_OF_DEP, EET, FLIGHT_RULES, ROUTE, COMMENTS = range(14)
	
	detailStrNames = {
		CALLSIGN: 'CALLSIGN',
		ACFT_TYPE: 'ACFT',
		WTC: 'WTC',
		ICAO_DEP: 'DEP_AD',
		ICAO_ARR: 'ARR_AD',
		ICAO_ALT: 'ALT_AD',
		CRUISE_ALT: 'CR_ALT',
		TAS: 'TAS',
		SOULS: 'SOULS',
		TIME_OF_DEP: 'DEP_TIME',
		EET: 'EET',
		FLIGHT_RULES: 'RULES',
		ROUTE: 'ROUTE',
		COMMENTS: 'COMMENTS'
	}
	# End STATIC
	
	def __init__(self, details={}):
		self.online_id = None
		self.online_status = None # normally None only if FPL is not online
		self.online_comments = []
		self.modified_details = {} # detail modified since online download -> old value
		self.details = { detail:None for detail in FPL.details }
		self.details.update(details)
		self.strip_auto_printed = False
	
	def __str__(self):
		if self.online_id == None:
			return 'Local-%x' % id(self)
		else:
			return 'Online-%d' % self.online_id
		
	
	## ACCESS
	
	def __getitem__(self, detail):
		assert detail in FPL.details, 'Not a valid flight plan detail key'
		return self.details[detail]
	
	def existsOnline(self):
		return self.online_id != None
	
	def needsUpload(self):
		return len(self.modified_details) > 0
	
	def status(self):
		return self.online_status
	
	def onlineComments(self):
		return self.online_comments
	
	
	## QUERY
	
	def ETA(self):
		dep = self.details[FPL.TIME_OF_DEP]
		eet = self.details[FPL.EET]
		return dep + eet if dep != None and eet != None else None
	
	def flightIsInTimeWindow(self, half_width, ref=None, strict=False):
		dep = self.details[FPL.TIME_OF_DEP]
		if dep == None:
			return False
		if ref == None:
			ref = now()
		lo = ref - half_width
		hi = ref + half_width
		eta = some(self.ETA(), dep)
		if strict:
			return dep >= lo and eta <= hi
		else: 
			return dep <= hi and eta >= lo
	
	def shortDescr(self):
		return '%s, %s, %s' % (some(self.details[FPL.CALLSIGN], '?'), self.shortDescr_AD(), self.shortDescr_time())
	
	def shortDescr_AD(self):
		dep = self.details[FPL.ICAO_DEP]
		arr = self.details[FPL.ICAO_ARR]
		if dep != None and dep == arr:
			return '%s local' % dep
		else:
			return '%s to %s' % (some(dep, '?'), some(arr, '?'))
	
	def shortDescr_time(self):
		if self.status() == FPL.OPEN:
			eta = self.ETA()
			if eta != None:
				return 'ARR %s' % rel_datetime_str(eta, longFormat=True)
		tdep = self.details[FPL.TIME_OF_DEP]
		return 'DEP %s' % rel_datetime_str(tdep, longFormat=True) if tdep != None else '?'
	
	
	## MODIFY
	
	def markAsOnline(self, online_id):
		self.online_id = online_id
		self.online_status = FPL.FILED
	
	def setOnlineStatus(self, status):
		self.online_status = status
	
	def setOnlineComments(self, comment_list):
		self.online_comments = comment_list

	def __setitem__(self, detail, new_value):
		assert detail in FPL.details, 'Incorrect FPL detail key: %s' % detail
		if new_value == '':
			new_value = None
		old_value = self.details[detail]
		if new_value != old_value:
			self.details[detail] = new_value
			if self.existsOnline() and detail not in self.modified_details:
				self.modified_details[detail] = old_value
	
	def revertToOnlineValues(self):
		for d, v in self.modified_details.items():
			self.details[d] = v
		self.modified_details.clear()

