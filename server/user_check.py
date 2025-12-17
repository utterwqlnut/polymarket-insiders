from websockets.asyncio.client import connect
import json
import requests
import re
import asyncio
import numpy as np
from concurrent.futures import ProcessPoolExecutor 
from analysis import monte_carlo
import os
import aiohttp
import redis.asyncio as redis


class UserChecker:
    def __init__(self, priority_queue: asyncio.PriorityQueue, limit: int, num_runs: int, executor: ProcessPoolExecutor, session: aiohttp.ClientSession, redis: redis.Redis):
        self.pq = priority_queue 
        self.url_no_user = f"https://data-api.polymarket.com/closed-positions?limit={limit}&sortBy=TIMESTAMP&sortDirection=DESC&user="
        self.num_runs = num_runs
        self.executor = executor
        self.session = session
        self.r = redis

    async def pull_user(self,hash):
        async with self.session.get(self.url_no_user+hash) as resp:
            user_data = await resp.json()

            user_trades = []
            for trade in user_data:
                user_trades.append((trade["totalBought"],trade["realizedPnl"],trade['avgPrice']))

            return np.array(user_trades,dtype=np.float64)

    async def check_loop(self):
        '''
        Consumer of the Suspicous Price Changes Priority Queue
        Calls further user analysis
        '''
        while True:
            neg_size, counter, info_dict = await self.pq.get()
            size = neg_size * -1
            user_closed_trades = await self.pull_user(info_dict["user"])

            if len(user_closed_trades.shape) < 2:
                continue

            loop = asyncio.get_running_loop()

            prob = await loop.run_in_executor(
                self.executor,
                monte_carlo,
                user_closed_trades,
                self.num_runs,
            )

            await self.r.zadd("leaderboard",{info_dict["user"]:1-prob})
            await self.r.zremrangebyrank("leaderboard", 0, -1001)

