import asyncio
from typing import AsyncGenerator

from .pubs import BinancePub, BookPub, BTPub


async def create_book_consumer_generator(pub: BookPub) -> AsyncGenerator:
    prev_book = None
    while True:
        book = pub.book
        if book and book != prev_book:
            yield book
            prev_book = book
        await asyncio.sleep(0)


async def create_binance_consumer_generator(pub: BinancePub) -> AsyncGenerator:
    seen = 0
    while True:
        if pub.mid and pub.books_seen > seen:
            seen = pub.books_seen
            yield pub.mid
        await asyncio.sleep(0.004)


async def create_bt_consumer_generator(pub: BTPub) -> AsyncGenerator:
    seen = 0
    while True:
        if pub.bid and pub.ask and pub.books_seen > seen:
            seen = pub.books_seen
            yield pub.bid, pub.ask
        await asyncio.sleep(0.020)
