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

async def start_api(app):
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
    )

    server = uvicorn.Server(config)
    await server.serve()


async def run():
    executor = ProcessPoolExecutor(max_workers=os.cpu_count())
    session = aiohttp.ClientSession()
    args = get_args()

    redis_client = redis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
        ssl=True,   # REQUIRED on Railway
    )


    pq = asyncio.PriorityQueue()
    api = FlagAPI(args.suspicious_size,pq,args.max_trades_per_call,args.rate,session)
    uc = UserChecker(pq,args.limit_history,args.monte_carlo_runs,executor,session,r)

    app = create_app(r)
    
    try:
        await asyncio.gather(api.get_latest_trades(),uc.check_loop(),start_api(app))
    finally:
        await session.close()
        await r.close()
        executor.shutdown(wait=False)

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()