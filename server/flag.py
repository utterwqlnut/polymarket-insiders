import json
import re
import asyncio
import itertools
import copy
import time
import aiohttp

class FlagAPI:
    def __init__(self,
                 suspicious_size: float, 
                 priority_queue: asyncio.PriorityQueue, 
                 max_trades_per_call: int,
                 rate: int,
                 session: aiohttp.ClientSession):

        self.suspicious_size = suspicious_size
        self.priority_queue = priority_queue
        self.counter = itertools.count()
        self.url = f"https://data-api.polymarket.com/trades?limit={max_trades_per_call}&takerOnly=true&offset=0&filterType=CASH&filterAmount={suspicious_size}"
        self.rate = rate
        
        self.last_ts = None
        self.last_hash = ""
        self.lock = asyncio.Lock()
        self.session = session

    async def fetch(self,url):
        async with self.session.get(url) as resp:
            return await resp.json()

    async def get_latest_trades(self):
        while True:
            await self.suspicious_message_handle(self.url)
            await asyncio.sleep(self.rate)

    async def suspicious_message_handle(self,url):
        '''
        Producer: Flags excessivly large orders and enqueues them to the pq 
        for user further analysis
        '''
        trades_json = await self.fetch(url)

        async with self.lock:
            last_ts_ = self.last_ts
            last_hash_ = self.last_hash

        for i,trade in enumerate(trades_json):
            if i == 0:
                async with self.lock:
                    self.last_ts = float(trade["timestamp"])
                    self.last_hash = trade["transactionHash"]

            if last_ts_ != None and ( float(trade["timestamp"]) < last_ts_ or trade['transactionHash'] == last_hash_):
                break

            await self.priority_queue.put((-1*float(trade["size"]),
                                            next(self.counter),
                                            {"market_id": trade["conditionId"],
                                                            "asset_id": trade["asset"],
                                                            "trade_hash": trade["transactionHash"],
                                                            "user": trade["proxyWallet"],
                                                            "timestamp": float(trade['timestamp'])}))

    async def close(self):
        if self.session:
            await self.session.close()