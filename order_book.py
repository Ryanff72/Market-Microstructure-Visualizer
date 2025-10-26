import threading
from collections import deque

# stores live order book for btc.

class OrderBook:
	def __init__(self):
		# dicts for asks and buys
		# price -> size
		self.bids = {}
		self.asks = {}

		# safety - websocket runs on different thread
		self.lock = threading.Lock()

		# chart history
		self.spread_history = deque(maxlen=300)
		self.mid_price_history = deque(maxlen=300)
		self.imbalance_history = deque(maxlen=300)

	# called when recieve initial snapshot
	# converts lists into our dictionaries
	def initialize_snapshot(self, bids_list, asks_list):
		with self.lock:
			self.bids.clear()
			self.asks.clear()
			for price, size in bids_list:
				self.bids[float(price)] = float(size)
			for price, size in asks_list:
				self.asks[float(price)] = float(size)
			print(f"+ Initialized {len(self.bids)} bids, {len(self.asks)} asks +")
	
	# called upon updates to update book
	def process_update(self, changes):
		with self.lock:
			for side, price, size in changes:
				if side == "buy":
					# if size 0 remove from list
					if float(size) == 0:
						self.bids.pop(float(price), None)
					else:
						self.bids[float(price)] = float(size)
				elif side == "sell":
					if float(size) == 0:
						self.asks.pop(float(price), None)
					else:
						self.asks[float(price)] = float(size)
	# get highest bid
	def get_best_bid(self):
		with self.lock:
			if self.bids:
				return max(self.bids.keys())
			else:
				return None

	# get highest ask
	def get_best_ask(self):
		with self.lock:
			if self.asks:
				return min(self.asks.keys())
			else:
				return None

	# get spread (best ask - best bid)
	# remember, less spread means more liquidity.
	def get_spread(self):
		with self.lock:
			if self.asks and self.bids:
				return  min(self.asks.keys()) - max(self.bids.keys())
			else:
				return None
	
	# get price average of best bid and ask
	def get_mid_price(self):
		with self.lock:
			if self.asks and self.bids:
				return (max(self.bids.keys()) + min(self.asks.keys())) / 2
			else:
				return None
	
	# get imbalance (buy vs sell pressure)
	# remember, imbalance = bid_vol / (bid_vol + ask_vol)
	# we use top 10 bid values and ask values to calculate this
	# if == 0.5, balanced. > 0.5 -> buy pressure, < 0.5 -> sell pressure
	def get_imbalance(self):
		with self.lock:
			if self.asks and self.bids:
				top_ten_bids = sorted(self.bids.items(), reverse=True)[:10]
				bid_volume = sum(size for price, size in top_ten_bids)
				top_ten_asks = sorted(self.asks.items())[:10]
				ask_volume = sum(size for price, size in top_ten_asks)
				return bid_volume / (bid_volume + ask_volume)
			else:
				return None
	
	# get depth snapshot (top N price levels)
	def get_depth_snapshot(self, levels=10):
		with self.lock:
			sorted_bids = sorted(self.bids.items(), reverse = True)[:levels]
			sorted_asks = sorted(self.asks.items())[:levels]
			return {
				'bids': sorted_bids,
				'asks': sorted_asks
			}

	# store metrics in history for charting
	# this is called every second to build historical data
	# appends to spread history, mid price history, and imbalance history
	def update_history(self):
		self.spread_history.append(self.get_spread())
		self.mid_price_history.append(self.get_mid_price())
		self.imbalance_history.append(self.get_imbalance())

	# gets all metrics at once
	def get_metrics(self):
		return {	
			'best_bid': self.get_best_bid(),
			'best_ask': self.get_best_ask(),
			'spread': self.get_spread(),
			'mid_price': self.get_mid_price(),
			'imbalance': self.get_imbalance()
		}