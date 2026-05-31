import asyncio
import time
from typing import Optional, Tuple

import aiohttp
import numpy as np
import redis.asyncio as redis
from concurrent.futures import ProcessPoolExecutor

from analysis import monte_carlo

USER_META_KEY = "user_meta:{user}"


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
        max_trading_age_days: int,
        executor: ProcessPoolExecutor,
        session: aiohttp.ClientSession,
        redis: redis.Redis,
        num_workers: int,
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
        self.url_first_trade = (
            "https://data-api.polymarket.com/activity"
            "?limit=1&type=TRADE&sortBy=TIMESTAMP&sortDirection=ASC&user="
        )
        self.num_runs = num_runs
        self.max_trading_age_days = max_trading_age_days
        self.executor = executor
        self.session = session
        self.r = redis
        self.num_workers = num_workers
        self._ready_queue: asyncio.Queue = asyncio.Queue(maxsize=num_workers * 4)

    def _meta_key(self, user: str) -> str:
        return USER_META_KEY.format(user=user)

    async def warmup(self) -> None:
        """Hit wallet endpoints once to warm DNS/TLS and the aiohttp pool."""
        user = "0x0000000000000000000000000000000000000001"
        await asyncio.gather(
            self._fetch_json(self.url_no_user + user),
            self._fetch_json(self.url_cur_pos_no_user + user),
            self._fetch_json(self.url_first_trade + user),
        )

    async def get_trading_age(self, user: str) -> Tuple[Optional[float], Optional[int]]:
        """
        Return (trading_age_days, first_trade_ts) from cache or the activity API.
        trading_age_days is days since the user's first TRADE event.
        """
        meta_key = self._meta_key(user)
        cached_ts = await self.r.hget(meta_key, "first_trade_ts")

        if cached_ts is not None:
            first_ts = int(float(cached_ts))
        else:
            async with self.session.get(self.url_first_trade + user) as resp:
                activity = await resp.json()

            if not activity:
                return None, None

            first_ts = int(activity[0]["timestamp"])
            await self.r.hset(meta_key, mapping={"first_trade_ts": first_ts})

        trading_age_days = (time.time() - first_ts) / 86400.0
        await self.r.hset(meta_key, "trading_age_days", trading_age_days)
        return trading_age_days, first_ts

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
        closed_data, open_data = await asyncio.gather(
            self._fetch_json(self.url_no_user + user),
            self._fetch_json(self.url_cur_pos_no_user + user),
        )
        user_data = closed_data + open_data

        user_trades = [
            (
                trade["totalBought"],
                trade["curPrice"],
                trade["avgPrice"],
            )
            for trade in user_data
        ]

        return np.array(user_trades, dtype=np.float64)

    async def _fetch_json(self, url: str) -> list:
        async with self.session.get(url) as resp:
            return await resp.json()

    async def _fetch_worker(self):
        """Prefetch wallet data while scorers run Monte Carlo."""
        while True:
            _neg_size, _counter, info_dict = await self.pq.get()
            user = info_dict["user"]

            trading_age_days, first_trade_ts = await self.get_trading_age(user)
            if trading_age_days is None:
                continue

            if (
                self.max_trading_age_days > 0
                and trading_age_days > self.max_trading_age_days
            ):
                continue

            user_closed_trades = await self.pull_user(user)

            if user_closed_trades.ndim < 2:
                continue

            await self._ready_queue.put(
                (user, user_closed_trades, trading_age_days, first_trade_ts)
            )

    async def _score_worker(self):
        """Run Monte Carlo on prefetched wallets to keep the process pool busy."""
        loop = asyncio.get_running_loop()

        while True:
            user, user_closed_trades, trading_age_days, first_trade_ts = (
                await self._ready_queue.get()
            )

            prob = await loop.run_in_executor(
                self.executor,
                monte_carlo,
                user_closed_trades,
                self.num_runs,
            )

            meta_key = self._meta_key(user)
            await self.r.hset(
                meta_key,
                mapping={
                    "first_trade_ts": first_trade_ts,
                    "trading_age_days": trading_age_days,
                    "insider_score": 1.0 - prob,
                },
            )

            await self.r.zadd("leaderboard", {user: 1.0 - prob})
            await self.r.zremrangebyrank("leaderboard", 0, -1001)

    async def check_loop(self):
        """Fetchers fill the ready queue while scorers saturate the process pool."""
        num_fetchers = self.num_workers * 2
        tasks = [self._fetch_worker() for _ in range(num_fetchers)]
        tasks += [self._score_worker() for _ in range(self.num_workers)]
        await asyncio.gather(*tasks)
