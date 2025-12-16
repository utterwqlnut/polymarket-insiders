from flag import FlagAPI
from user_check import UserChecker
import asyncio

async def run():
    pq = asyncio.PriorityQueue()
    api = FlagAPI(1000,pq,1000,60)
    uc = UserChecker(pq,100)
    await asyncio.gather(api.get_latest_trades(),uc.check_loop())

asyncio.run(run())