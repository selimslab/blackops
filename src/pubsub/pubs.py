import asyncio
from dataclasses import dataclass
from datetime import datetime
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
    last_updated = datetime.now()

    async def run(self):
        await self.consume_stream()

    async def consume_stream(self):
        if not self.stream:
            raise ValueError("No stream")
        if not self.api_client:
            raise ValueError("No api_client")

        async for book in self.stream:
            # new_quote = self.exchange.get_mid(book)
            self.book = book
            self.last_updated = datetime.now()
            self.books_seen += 1
            await asyncio.sleep(0)


PubsubProducer = Union[BalancePub, BookPub]
