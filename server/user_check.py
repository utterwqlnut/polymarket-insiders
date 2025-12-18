import asyncio
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import aiohttp
import redis.asyncio as redis

from analysis import monte_carlo


class UserChecker:
    """
    Consumes flagged trades and evaluates whether a user's performance
    can be explained by chance.

    Heavy computation is offloaded to a ProcessPoolExecutor to avoid
    blocking the event loop.
    """

    def __init__(
        self,
        priority_queue: asyncio.PriorityQueue,
        limit: int,
        num_runs: int,
        executor: ProcessPoolExecutor,
        session: aiohttp.ClientSession,
        redis: redis.Redis,
    ):
        self.pq = priority_queue
        self.url_no_user = (
            "https://data-api.polymarket.com/closed-positions"
            f"?limit={limit}"
            "&sortBy=TIMESTAMP"
            "&sortDirection=DESC"
            "&user="
        )
        self.url_cur_pos_no_user = (
            "https://data-api.polymarket.com/positions"
            f"?limit={limit}"
            "&sortBy=RESOLVING"
            "&sortDirection=ASC"
            "&user="
        )
        self.num_runs = num_runs
        self.executor = executor
        self.session = session
        self.r = redis

    async def pull_user(self, user: str) -> np.ndarray:
        """
        Fetch and normalize a user's closed positions.

        Returns
        -------
        np.ndarray
            Array of shape (N, 3):
                [0] total position size
                [1] realized PnL
                [2] average entry price (used as win probability proxy)
        """
        async with self.session.get(self.url_no_user + user) as resp:
            user_data = await resp.json()
        
        async with self.session.get(self.url_cur_pos_no_user + user) as resp:
            user_cur_position_data = await resp.json()

        user_data += user_cur_position_data

        user_trades = [
            (
                trade["totalBought"],
                trade["curPrice"],
                trade["avgPrice"],
            )
            for trade in user_data
        ]

        return np.array(user_trades, dtype=np.float64)

    async def check_loop(self):
        """
        Continuously process flagged users from the priority queue.
        This method runs indefinitely and should be launched
        as a background task.
        """
        while True:
            neg_size, counter, info_dict = await self.pq.get()
            user = info_dict["user"]

            user_closed_trades = await self.pull_user(user)
            
            if len(user_closed_trades) > 100:
                continue
            # Skip users with insufficient data
            if user_closed_trades.ndim < 2:
                continue

            loop = asyncio.get_running_loop()

            prob = await loop.run_in_executor(
                self.executor,
                monte_carlo,
                user_closed_trades,
                self.num_runs,
            )

            # Store inverse probability so higher scores rank first
            await self.r.zadd("leaderboard", {user: 1.0 - prob})

            # Keep only the top 1000 users
            await self.r.zremrangebyrank("leaderboard", 0, -1001)
