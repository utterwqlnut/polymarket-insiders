from flag import FlagAPI
from user_check import UserChecker
import asyncio
from concurrent.futures import ProcessPoolExecutor 
import os
import aiohttp
import redis.asyncio as redis
import uvicorn
from api_endpoints import create_app

async def start_api(app):
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run():
    executor = ProcessPoolExecutor(max_workers=os.cpu_count())
    session = aiohttp.ClientSession()
    r = redis.Redis(host='localhost', port=6379, db=0)

    pq = asyncio.PriorityQueue()
    api = FlagAPI(1000,pq,1000,5,session)
    uc = UserChecker(pq,100,10000,executor,session,r)

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