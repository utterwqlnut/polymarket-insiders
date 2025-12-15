from websockets.asyncio.client import connect
import json
import requests
import re
import asyncio
import itertools

class FlagAPI:
    def __init__(self,num_markets: int, suspicious_size: float, priority_queue: asyncio.PriorityQueue):
        self.market_tokens = FlagAPI.get_market_tokens(num_markets)
        self.suspicious_size = suspicious_size
        self.priority_queue = priority_queue
        self.counter = itertools.count()

    def get_market_tokens(num_markets: int):
        market_result = requests.get(f"https://gamma-api.polymarket.com/markets?limit={num_markets}&closed=false")
        
        if market_result.status_code != 200:
            print("Unable to connect to polymarket api please try again")
            raise Exception("Failed to connect")

        markets = market_result.json()
        
        tokens = [token 
                  for market in markets 
                  for token in re.findall(r"[0-9]+",market["clobTokenIds"])]

        return tokens
    
    async def websockets(self):
        async with connect("wss://ws-subscriptions-clob.polymarket.com/ws/market") as websocket:
            await websocket.send(json.dumps({
                "assets_ids": self.market_tokens,
                "type": "market"
            }))

            while True:
                asyncio.create_task(
                    self.suspicious_message_handle(await websocket.recv()
                ))

    async def suspicious_message_handle(self,msg):
        msg_json = json.loads(msg)
        if msg_json['event_type'] == 'price_change':
            for order in msg_json['price_changes']:
                if float(order['size']) > self.suspicious_size:
                    print(msg_json)
                    await self.priority_queue.put((-1*float(order["size"]),
                                                   next(self.counter),
                                                   {"market_id": msg_json["market"],
                                                                    "asset_id": order["asset_id"],
                                                                    "order_hash": order["hash"],
                                                                    "order_size": float(order["size"]),
                                                                    "timestamp": float(msg_json['timestamp'])}))
pq = asyncio.PriorityQueue()
api = FlagAPI(30000,100000,pq)
asyncio.run(api.websockets())
