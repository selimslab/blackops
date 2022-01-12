import asyncio
from typing import AsyncGenerator

from .pubs import BookPub


async def create_book_consumer_generator(pub: BookPub) -> AsyncGenerator:
    prev_book = None
    while True:
        book = pub.book
        if book and book != prev_book:
            yield book
            prev_book = book
        await asyncio.sleep(0.02)
