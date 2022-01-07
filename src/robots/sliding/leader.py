import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator, AsyncIterable


@dataclass
class LeaderWatcher:
    book_stream: AsyncGenerator
    theo_last_updated: datetime = datetime.now()
    books_seen: int = 0

    async def book_generator(self) -> AsyncIterable:
        async for book in self.book_stream:
            yield book
            self.books_seen += 1
            self.theo_last_updated = datetime.now()
            await asyncio.sleep(0)
