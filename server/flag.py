import asyncio
import itertools
import aiohttp


class FlagAPI:
    """
    Polls the Polymarket trades API and flags unusually large trades.
    This class acts as a producer in the async pipeline
    """

    def __init__(
        self,
        suspicious_size: float,
        priority_queue: asyncio.PriorityQueue,
        max_trades_per_call: int,
        rate: int,
        session: aiohttp.ClientSession,
    ):
        self.suspicious_size = suspicious_size
        self.priority_queue = priority_queue
        self.counter = itertools.count()

        self.url = (
            "https://data-api.polymarket.com/trades"
            f"?limit={max_trades_per_call}"
            "&takerOnly=true"
            "&offset=0"
            "&filterType=CASH"
            f"&filterAmount={suspicious_size}"
        )

        self.rate = rate
        self.session = session

        self.last_ts = None
        self.last_hash = ""
        self.lock = asyncio.Lock()

    async def fetch(self, url):
        """Fetch JSON data from the Polymarket trades API."""
        async with self.session.get(url) as resp:
            return await resp.json()

    async def get_latest_trades(self):
        """
        Continuously poll the trades API at a fixed rate.
        This method runs indefinitely and should be executed as a background task.
        """
        while True:
            await self._handle_suspicious_trades(self.url)
            await asyncio.sleep(self.rate)

    async def _handle_suspicious_trades(self, url):
        """
        Fetch recent trades and enqueue new suspicious ones.
        Trades are processed in descending time order. Once a previously seen
        trade is encountered, processing stops to avoid duplicate work.
        """
        trades_json = await self.fetch(url)

        async with self.lock:
            last_ts_ = self.last_ts
            last_hash_ = self.last_hash

        for i, trade in enumerate(trades_json):
            # Update the most recent trade marker
            if i == 0:
                async with self.lock:
                    self.last_ts = float(trade["timestamp"])
                    self.last_hash = trade["transactionHash"]

            # Stop once we reach trades already processed
            if (
                last_ts_ is not None
                and (
                    float(trade["timestamp"]) < last_ts_
                    or trade["transactionHash"] == last_hash_
                )
            ):
                break

            # Push into priority queue (largest trades first)
            await self.priority_queue.put(
                (
                    -float(trade["size"]),
                    next(self.counter),
                    {
                        "market_id": trade["conditionId"],
                        "asset_id": trade["asset"],
                        "trade_hash": trade["transactionHash"],
                        "user": trade["proxyWallet"],
                        "timestamp": float(trade["timestamp"]),
                    },
                )
            )

    async def close(self):
        """Close the underlying HTTP session."""
        if self.session:
            await self.session.close()
