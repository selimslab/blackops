import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Optional, Union

from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import periodic


@dataclass
class PublisherBase:
    pubsub_key: str

    async def run(self):
        pass


@dataclass
class BalancePub(PublisherBase):
    exchange: ExchangeAPIClientBase
    last_updated = datetime.now()
    balances: Optional[dict] = None

    async def run(self):
        coros = [
            periodic(
                self.ask_balance,
                sleep_seconds.update_balances,
            ),
            periodic(
                self.exchange.clear_orders_in_last_second,
                0.97,
            ),
        ]

        await asyncio.gather(*coros)

    async def ask_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            self.balances = res
            self.last_updated = datetime.now()


@dataclass
class BookPub(PublisherBase):
    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase

    book: Optional[Union[str, dict]] = None
    books_seen: int = 0
    prev_book: Optional[Union[str, dict]] = None
    # last_updated = datetime.now()

    async def run(self):
        await self.consume_stream()

    async def consume_stream(self):
        if not self.stream:
            raise ValueError("No stream")
        if not self.api_client:
            raise ValueError("No api_client")

        async for book in self.stream:
            if book and book != self.prev_book:
                self.book = book
                self.prev_book = book
                self.books_seen += 1
            await asyncio.sleep(0)


@dataclass
class BinancePub(PublisherBase):

    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase
    mids: list = field(default_factory=list)
    books_seen: int = 0

    def get_mid(self):
        if len(self.mids) == 0:
            return None
        mid = sum(self.mids) / len(self.mids)
        self.mids = []
        return Decimal(mid)

    async def run(self):
        await self.consume_stream()

    async def consume_stream(self):
        if not self.stream:
            raise ValueError("No stream")

        async for book in self.stream:
            if book:
                try:
                    if "data" in book:
                        mid = (float(book["data"]["a"]) + float(book["data"]["b"])) / 2
                        self.mids.append(mid)
                        self.books_seen += 1
                except Exception as e:
                    continue


PubsubProducer = Union[BalancePub, BookPub, BinancePub]
