import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator

from blackops.exchanges.base import ExchangeBase
from blackops.robots.config import SlidingWindowConfig
from blackops.util.logger import logger


@dataclass
class LeaderWatcher:
    book_stream: AsyncGenerator
    theo_last_updated: datetime = datetime.now()
    books_seen: int = 0

    async def book_generator(self):
        async for book in self.book_stream:
            if book:
                self.books_seen += 1
                yield book
                self.theo_last_updated = datetime.now()
            await asyncio.sleep(0)
