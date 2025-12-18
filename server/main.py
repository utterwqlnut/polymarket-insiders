from flag import FlagAPI
from user_check import UserChecker
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os
import aiohttp
import redis.asyncio as redis
import uvicorn
from api_endpoints import create_app
from argparsing import get_args
import logging

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
    
    executor = ProcessPoolExecutor(max_workers=os.cpu_count())
    session = aiohttp.ClientSession()
    args = get_args()
    
    r = redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
    )
    
    pq = asyncio.PriorityQueue()
    api = FlagAPI(args.suspicious_size, pq, args.max_trades_per_call, args.rate, session)
    uc = UserChecker(pq, args.limit_history, args.monte_carlo_runs, executor, session, r)
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