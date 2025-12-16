from websockets.asyncio.client import connect
import json
import requests
import re
import asyncio
import itertools

class UserChecker:
    def __init__(self, priority_queue: asyncio.PriorityQueue,limit: int):
        self.pq = priority_queue 
        self.url_no_user = f"https://data-api.polymarket.com/closed-positions?limit={limit}&sortBy=TIMESTAMP&sortDirection=DESC&user="
    
    async def pull_user(self, hash):
        url = self.url_no_user+hash
        user_result = requests.get(url)
        
        if user_result.status_code != 200:
            print("Unable to connect to polymarket api please try again")
            raise Exception("Failed to connect")

        user_data = user_result.json()
        user_trades = []
        for trade in user_data:
            user_trades.append((trade["realizedPnl"],trade["totalBought"]))
        
        return user_trades

    async def check_loop(self):
        '''
        Consumer of the Suspicous Price Changes Priority Queue
        Calls further user analysis
        '''
        while True:
            neg_size, counter, info_dict = await self.pq.get()
            size = neg_size * -1
            
            user_closed_trades = await self.pull_user(info_dict["user"])
            
    


