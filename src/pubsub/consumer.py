import asyncio
from typing import AsyncGenerator

from .pubs import BinancePub, BookPub


async def create_book_consumer_generator(pub: BookPub) -> AsyncGenerator:
    prev_book = None
    while True:
        book = pub.book
        if book and book != prev_book:
            yield book
            prev_book = book
        await asyncio.sleep(0.01)


async def create_binance_consumer_generator(pub: BinancePub) -> AsyncGenerator:
    while True:
        mid = pub.get_mid()
        if mid:
            yield mid
        await asyncio.sleep(0.01)
