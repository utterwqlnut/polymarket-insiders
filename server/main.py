from flag import FlagAPI
from user_check import UserChecker
import asyncio
from concurrent.futures import ProcessPoolExecutor 
import os
import aiohttp

async def run():
    executor = ProcessPoolExecutor(max_workers=os.cpu_count())
    session = aiohttp.ClientSession()

    pq = asyncio.PriorityQueue()
    api = FlagAPI(1000,pq,1000,5,session)
    uc = UserChecker(pq,100,10,executor,session)
    
    try:
        await asyncio.gather(api.get_latest_trades(),uc.check_loop())
    finally:
        await session.close()

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()