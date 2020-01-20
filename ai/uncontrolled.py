from ai.baseAcft import AbstractAiAcft
from data.params import distance_flown


# ---------- Constants ----------

# -------------------------------



class UncontrolledAircraft(AbstractAiAcft):
	'''
	This class represents an AI aircraft NOT in radio contact (uncontrolled), that just flies around.
	Used as disctractors in solo sessions.
	'''
	def __init__(self, callsign, acft_type, init_params, ticks_to_live):
		AbstractAiAcft.__init__(self, callsign, acft_type, init_params)
		self.ticks_to_live = ticks_to_live
	
	
	def doTick(self):
		self.params.position = self.params.position.moved(self.params.heading, distance_flown(self.tick_interval, self.params.ias))
		self.ticks_to_live -= 1
