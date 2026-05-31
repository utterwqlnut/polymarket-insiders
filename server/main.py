from flag import FlagAPI
from user_check import UserChecker
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os
import aiohttp
import numpy as np
import redis.asyncio as redis
import uvicorn
from api_endpoints import create_app
from argparsing import get_args
from analysis import monte_carlo
import logging

_WARMUP_SAMPLE = np.array(
    [[100.0, 1.0, 0.6], [50.0, 0.0, 0.4]],
    dtype=np.float64,
)


def _warmup_numba_worker(num_runs: int) -> None:
    """Compile Numba in a process-pool worker."""
    monte_carlo(_WARMUP_SAMPLE, num_runs)


async def warmup_numba(
    executor: ProcessPoolExecutor, num_workers: int, num_runs: int
) -> None:
    """Spawn every pool worker and JIT-compile monte_carlo before real traffic."""
    warmup_runs = min(num_runs, 500)
    loop = asyncio.get_running_loop()
    await asyncio.gather(
        *[
            loop.run_in_executor(executor, _warmup_numba_worker, warmup_runs)
            for _ in range(num_workers)
        ]
    )


async def warmup_http(flag_api: FlagAPI, user_checker: UserChecker) -> None:
    """Warm Polymarket HTTP connections before fetch workers start."""
    await asyncio.gather(
        flag_api.warmup(),
        user_checker.warmup(),
        return_exceptions=True,
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_api(app):
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()

async def run():
    # Validate environment
    if "REDIS_URL" not in os.environ:
        raise ValueError("REDIS_URL environment variable not set")
    
    num_workers = os.cpu_count() or 1
    executor = ProcessPoolExecutor(max_workers=num_workers)
    session = aiohttp.ClientSession()
    args = get_args()

    r = redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )

    pq = asyncio.PriorityQueue()
    api = FlagAPI(args.suspicious_size, pq, args.max_trades_per_call, args.rate, session)
    uc = UserChecker(
        pq,
        args.limit_history,
        args.monte_carlo_runs,
        args.max_trading_age_days,
        executor,
        session,
        r,
        num_workers,
    )

    await warmup_numba(executor, num_workers, args.monte_carlo_runs)
    await warmup_http(api, uc)

    app = create_app(r)

    tasks = [
        asyncio.create_task(api.get_latest_trades()),
        asyncio.create_task(uc.check_loop()),
        asyncio.create_task(start_api(app))
    ]
    
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        
        # Check for exceptions
        for task in done:
            if task.exception():
                logger.error(f"Task failed: {task.exception()}")
                raise task.exception()
                
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
    finally:

        for task in tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Cleanup resources
        await session.close()
        await r.close()
        executor.shutdown(wait=True, cancel_futures=True)
        logger.info("Cleanup complete")

def main():
    """
    Main entry point for the trading monitoring system.
    Runs three concurrent services:
    - FlagAPI: Monitors trading activity
    - UserChecker: Validates user behavior
    - API Server: Provides REST endpoints
    """
    try:
        asyncio.run(run())
    except Exception as e:
        logger.error(f"Application failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()