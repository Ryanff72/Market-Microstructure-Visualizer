import json
import websocket
import threading
import time

# connects to coinbase and subscribes to btc-usd order book
# we will use this to get real time updates and data insights
class CoinbaseWebSocket:
	def __init__(self, on_message_callback=None):
		self.url = "wss://ws-feed.exchange.coinbase.com"
		self.product_id = "BTC-USD"
		self.ws = None #websocket
		self.callback = on_message_callback
		self.running = False #connected?

	# when socket opens
	def on_open(self, ws):
		print("+ Coinbase Connected +")

		# request
		sub_message = {
			"type": "subscribe",
			"product_ids": [self.product_id],
			"channels": ["level2_batch"] #order book
		}

		# send message
		ws.send(json.dumps(sub_message))
		print(f"+ subscribed successfully to {self.product_id} order book +")
	
	# called when a response is recieved
	def on_message(self, ws, message):
		try:
			data = json.loads(message) #dict of data
			msg_type = data.get("type")
			'''
			if msg_type == "snapshot":
				print(f"Snap: {len(data.get('bids',[]))} bids, {len(data.get('asks',[]))} asks")
			elif msg_type == "l2update":
				print(f"Update noticed: {len(data.get('changes', []))} changed")
			'''

			#call orderbook update
			if self.callback:
				self.callback(msg_type, data)
		except json.JSONDecodeError:
			print(f"- Json parse failed: {message}-")

	# if error
	def on_error(self, ws, error):
		print(f"error: {error}")

	# when websocket closes
	def on_close(self, ws, close_status_code, close_msg):
		print("- Connection Closed Successfully -")
		self.running = False

	# starts websocket on it's own thread
	def start(self):
		self.running = True
		self.ws = websocket.WebSocketApp(
			self.url,
			on_open=self.on_open,
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close
		)

		# run on thread
		thread = threading.Thread(target=self.ws.run_forever)
		thread.daemon = True
		thread.start()

		print("+ Websocket started running in background... +")

	# stop connection (elegant)
	def stop(self):
		self.running = False
		if self.ws:
			self.ws.close()
		print("- Stopped - ")

# test class standalone
if __name__ == "__main__":
	def my_callback(msg_type, data):
		print(f"mycallback running. msg type: {msg_type}")
		if msg_type == "snapshot":
			bids = data.get('bids', [])
			asks = data.get('asks', [])
			print(f" got {len(bids)} bids and {len(asks)} asks")
			if bids:
				print(f" best bid: ${bids[0][0]} ({bids[0][1]} BTC)")
			if asks:
				print(f" best ask: ${asks[0][0]} ({asks[0][1]} BTC)")
		elif msg_type == "l2update":
			changes = data.get('changes', [])
			for change in changes:
				side, price, size = change
				if size == "0":
					print(f"{side} @ ${price} removed")
				else:
					print(f"{side} @ ${price}: {price} BTC")
	client = CoinbaseWebSocket(on_message_callback=my_callback)
	client.start()
	print("\nWatching orders for 20 seconds...\n")
	try:
		time.sleep(20)
	except KeyboardInterrupt:
		print("\n- User Interrupt (keypress) -\n")
	client.stop()
	print("+ finished. +")
