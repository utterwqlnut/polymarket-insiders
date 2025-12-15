from websockets.asyncio.client import connect
import json
import requests
import re
import asyncio
import itertools

class UserChecker:
    def __init__(self, priority_queue: asyncio.PriorityQueue):
        self.pq = priority_queue 

    async def check_loop(self):
        