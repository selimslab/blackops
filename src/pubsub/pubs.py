import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Optional, Union

from src.domain.models import Asset, AssetSymbol
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import StopwatchAPI, periodic
from src.proc import process_pool_executor, thread_pool_executor


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
    assets: Dict[AssetSymbol, Asset] = field(default_factory=dict)

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

    def add_asset(self, asset: Asset):
        if asset.symbol not in self.assets:
            self.assets[asset.symbol] = asset

    def get_asset(self, symbol: AssetSymbol):
        return self.assets.get(symbol)

    async def ask_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            # loop = asyncio.get_event_loop()
            # await loop.run_in_executor(thread_pool_executor, self.update_balances, res)
            self.update_balances(res)
            self.last_updated = datetime.now()

    def update_balances(self, balances) -> None:
        balance_dict: dict = self.exchange.parse_account_balance(balances)
        for symbol, asset in self.assets.items():
            data = balance_dict[symbol]
            asset.free = Decimal(data["free"])
            asset.locked = Decimal(data["locked"])


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
class BTPub(PublisherBase):
    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase

    books_seen: int = 0
    stopwatch: StopwatchAPI = field(default_factory=StopwatchAPI)

    # asks: List[Decimal] = field(default_factory=list)
    # bids: List[Decimal] = field(default_factory=list)

    ask: Decimal = Decimal(0)
    bid: Decimal = Decimal(0)

    async def run(self):
        await self.consume_stream()

    def parse_book(self, book):
        try:
            ask = self.api_client.get_best_ask(book)
            bid = self.api_client.get_best_bid(book)

            if ask and bid:
                self.ask = ask
                self.bid = bid
                self.books_seen += 1
        except Exception as e:
            logger.info(f"BTPub: {e}")
            return

    # def clear_prices(self):
    #     self.ask = None
    #     self.bid = None

    async def consume_stream(self):
        if not self.stream:
            raise ValueError("No stream")

        loop = asyncio.get_running_loop()
        async for book in self.stream:
            if book:
                await loop.run_in_executor(thread_pool_executor, self.parse_book, book)
            await asyncio.sleep(0)


@dataclass
class BinancePub(PublisherBase):

    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase
    books_seen: int = 0
    mid: Decimal = Decimal(0)

    mids: list = field(default_factory=list)

    def get_mid(self):
        if len(self.mids) == 0:
            return
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

            await asyncio.sleep(0)


PubsubProducer = Union[BalancePub, BookPub, BinancePub, BTPub]
