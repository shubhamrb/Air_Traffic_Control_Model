
from random import choice
from heapq import heappush, heappop


# ---------- Constants ----------

# -------------------------------


# =========================================
#   VALUE COMPARISONS and PAIRS/INTERVALS
# =========================================

def some(value, fallback):
	if value != None:
		return value
	return fallback


def noNone(value, failmsg=None):
	if value == None:
		raise ValueError(some(failmsg, 'Unaccepted None value'))
	return value


def rounded(value, step=1):
	return step * int((value + step / 2) / step)


def bounded(lower, value, upper):
	return min(max(lower, value), upper)


def ordered_pair(a, b):
	if a <= b:
		return a, b
	else:
		return b, a


def intervals_intersect(i1, i2):
	return i1[1] >= i2[0] and i2[1] >= i1[0]




# ===========
#    LISTS
# ===========


def pop_one(lst, pred):
	i = 0
	while i < len(lst):
		if pred(lst[i]):
			return lst.pop(i)
		i += 1
	raise StopIteration

def pop_all(lst, pred):
	i = 0
	result = []
	while i < len(lst):
		if pred(lst[i]):
			result.append(lst.pop(i))
		else:
			i+= 1
	return result



def all_diff(lst):
	return len(lst) == len(set(lst))

def flatten(ll):
	return [x for lst in ll for x in lst]



class PriorityQueue:
	def __init__(self):
		self.elements = []
	
	def empty(self):
		return len(self.elements) == 0
	
	def put(self, item, priority):
		heappush(self.elements, (priority, item))
	
	def get(self):
		return heappop(self.elements)[1]



class MultiSet:
	def __init__(self):
		self.elements = {} # T -> int count
	
	def __len__(self):
		return sum(self.elements.values())
	
	def __contains__(self, item):
		return item in self.elements
	
	def __str__(self):
		return '{ %s }' % ', '.join('%s x%d' % item_count for item_count in self.elements.items())
	
	def values(self):
		return set(self.elements.keys())
	
	def count(self, item):
		return self.elements.get(item, 0)
	
	def add(self, item, count=1):
		if count > 0:
			try:
				self.elements[item] += count
			except KeyError:
				self.elements[item] = count
	
	def remove_one(self, item):
		if self.elements[item] == 1:
			del self.elements[item]
		else:
			self.elements[item] -= 1
	
	def remove_all(self, item):
		del self.elements[item]
	
	def pop_one(self, pred):
		res = next(key for key in self.elements if pred(key))
		self.remove_one(res)
		return res
	
	def pop_any(self):
		key = list(self.elements)[0]
		self.remove_one(key)
		return key



# ============
#     MATH
# ============

def linear_function(x1, y1, x2, y2):
	return lambda x: ((y2 - y1) * x + (x2 * y1 - x1 * y2)) / (x2 - x1)



# =============
#    STRINGS
# =============

def random_string(length, chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
	result = ''
	for i in range(length):
		result += choice(chars)
	return result


def INET_addr_str(server, port):
	if ':' in server: # IPv6 address
		return '[%s]:%d' % (server, port)
	else:
		return '%s:%d' % (server, port)



# ===================
#    A-STAR SEARCH
# ===================

def A_star_search(src, goal, f_neighbours, heuristic=None):
	'''
	Types are:
	 - src and goal: T  # values used should be unique as they identify nodes of the graph
	 - f_neighbours: function T -> (T, num, T2/NoneType) list  # num for the cost of each hop; T2 for edge label (or None)
	 - heuristic if given: function T -> num
	Returns pair of lists (L1, L2) with same length:
	 - L1 = list of node hops from src to goal
	 - L2 = list of edge labels used on the way
	Returned lists are empty if src==goal, end with goal hop otherwise.
	Raises ValueError if no path is found.
	'''
	if src == goal:
		return [], []
	pqueue = PriorityQueue()
	pqueue.put(src, 0)
	came_from = {src: None}
	edge_to = {}
	cost_so_far = {src: 0}
	while not pqueue.empty():
		current_node = pqueue.get()
		if current_node == goal:
			break
		for next_node, hop_cost, next_edge in f_neighbours(current_node):
			new_cost = cost_so_far[current_node] + hop_cost
			if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
				cost_so_far[next_node] = new_cost
				h = 0 if heuristic == None else heuristic(next_node)
				pqueue.put(next_node, new_cost + h)
				came_from[next_node] = current_node
				edge_to[next_node] = next_edge
	if goal not in came_from: # no path to goal
		raise ValueError('No path to goal')
	res_nodes = [goal]
	res_edges = [edge_to[goal]]
	prev = came_from[goal]
	while prev != src:
		res_nodes.insert(0, prev)
		res_edges.insert(0, edge_to[prev])
		prev = came_from[prev]
	return res_nodes, res_edges

