
from datetime import datetime, timezone, timedelta


# ---------- Constants ----------

# -------------------------------




def now():
	return datetime.now(timezone.utc)


def timestr(t=None, seconds=False):
	if t == None:
		t = now()
	res = '%02d:%02d' % (t.hour, t.minute)
	if seconds:
		res += ':%02d' % t.second
	return res

def datestr(t=None, year=True):
	if t == None:
		t = now()
	res = '%d/%02d' % (t.day, t.month)
	if year:
		res += '/%d' % t.year
	return res

def rel_datetime_str(dt, longFormat=False, seconds=False):
	d = dt.date()
	if d == now().date():
		prefix = 'today at ' if longFormat else ''
	else: # not today
		prefix = datestr(d, year=False) + (' at ' if longFormat else ', ')
	return prefix + timestr(dt.time(), seconds=seconds)




def duration_str(td):
	seconds = int(round(td.total_seconds()))
	hours = seconds // 3600
	if hours == 0:
		return '%d min %02d s' % (seconds // 60, seconds % 60)
	else:
		return '%d h %02d min' % (hours, seconds % 3600 // 60)


last_stopwatch_reset = now()

def reset_stopwatch():
	global last_stopwatch_reset
	last_stopwatch_reset = now()


def read_stopwatch():
	'''
	returns a timedelta
	'''
	return (now() - last_stopwatch_reset).total_seconds()



