import asyncio
import collections
import statistics
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from re import S
from typing import AsyncGenerator, Dict, Optional, Union

import src.streams.bn as bn_streams
import src.streams.btcturk as btc_streams
from src.domain.models import BPS, DECIMAL_2, Asset, AssetSymbol
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
    assets: Dict[AssetSymbol, Asset] = field(default_factory=dict)

    async def run(self):
        coros = [
            periodic(
                self.publish_balance,
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

    async def publish_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            # loop = asyncio.get_event_loop()
            # await loop.run_in_executor(thread_pool_executor, self.update_balances, res)
            self.update_balances(res)
            # self.update_balances(res)
            self.last_updated = datetime.now()

    def update_balances(self, balances) -> None:
        balance_dict: dict = self.exchange.parse_account_balance(balances)
        for symbol, asset in self.assets.items():
            data = balance_dict[symbol]
            asset.free = Decimal(data["free"])
            asset.locked = Decimal(data["locked"])


@dataclass
class BTPub(PublisherBase):
    symbol: str
    api_client: ExchangeAPIClientBase

    books_seen: int = 0
    # stopwatch: StopwatchAPI = field(default_factory=StopwatchAPI)

    ask: Decimal = Decimal(0)
    mid: Decimal = Decimal(0)
    bid: Decimal = Decimal(0)

    book_stream: Optional[AsyncGenerator] = None

    def __post_init__(self):
        self.book_stream = btc_streams.create_book_stream(self.symbol)

    async def run(self):
        await self.publish_stream()

    def parse_book(self, book):
        try:
            ask = self.api_client.get_best_ask(book)
            bid = self.api_client.get_best_bid(book)

            if ask and bid:  # and (ask != self.ask or bid != self.bid)
                self.ask = ask
                self.bid = bid
                self.mid = (ask + bid) / DECIMAL_2
                self.books_seen += 1
        except Exception as e:
            logger.info(f"BTPub: {e}")
            return

    async def publish_stream(self):
        if not self.book_stream:
            raise ValueError("No stream")

        async for book in self.book_stream:
            if book:
                self.parse_book(book)
            await asyncio.sleep(0)


@dataclass
class RollingMean:
    maxlen: int
    total: Decimal = Decimal(0)
    count: Decimal = Decimal(0)

    def __post_init__(self):
        self.values = collections.deque(maxlen=self.maxlen)

    def add(self, value):
        if self.count < self.maxlen:
            self.values.append(value)
            self.count += 1
        else:
            self.total -= self.values.popleft()
            self.values.append(value)

        self.total += value

    def get_average(self):
        return self.total / self.count


@dataclass
class Slope:
    up: bool = False
    flat: bool = False
    down: bool = False

    diff: Decimal = Decimal(0)
    step: Decimal = Decimal(2)
    risk: Decimal = Decimal(0)


@dataclass
class BinancePub(PublisherBase):

    symbol: str
    api_client: ExchangeAPIClientBase
    books_seen: int = 0
    ask: Decimal = Decimal(0)
    mid: Decimal = Decimal(0)
    bid: Decimal = Decimal(0)
    spread_bps: Decimal = Decimal(0)

    book_stream: Optional[AsyncGenerator] = None

    slope: Slope = field(default_factory=Slope)

    # ma_small: RollingMean = field(default_factory=lambda: RollingMean(3))
    # ma_mid: RollingMean = field(default_factory=lambda: RollingMean(9))
    # ma_large: RollingMean = field(default_factory=lambda: RollingMean(27))
    # micro_ma_ok: bool = False

    def __post_init__(self):
        self.book_stream = bn_streams.create_book_stream(self.symbol)

    async def run(self):
        await asyncio.gather(self.publish_stream(), periodic(self.publish_klines, 5))

    def parse_book(self, book):
        try:
            if "data" in book:
                ask = Decimal(book["data"]["a"])
                bid = Decimal(book["data"]["b"])

                if ask and bid and (ask != self.ask or bid != self.bid):
                    self.ask = ask
                    self.bid = bid
                    mid = (ask + bid) / DECIMAL_2

                    self.spread_bps = (ask - bid) / mid / BPS

                    # self.ma_small.add(mid)
                    # self.ma_mid.add(mid)
                    # self.ma_large.add(mid)

                    if mid != self.mid:
                        # self.micro_ma_ok = bool(
                        #     self.ma_small.get_average()
                        #     > self.ma_mid.get_average()
                        #     > self.ma_large.get_average()
                        # )
                        self.mid = mid
                        self.books_seen += 1
        except Exception as e:
            logger.error(e)

    async def publish_klines(self):
        try:
            klines = await bn_streams.get_klines(self.symbol, interval="1m", limit=6)
            if klines:
                kline_closes = [Decimal(k[4]) for k in klines]

                former = statistics.mean(kline_closes[:5])
                latter = statistics.mean(kline_closes[1:])
                diff = latter - former

                bps_diff = diff / latter * BPS

                self.slope_risk = 4 - bps_diff

                self.slope.up = bool(bps_diff > 4)

                self.slope.down = bool(bps_diff < 1)

        except Exception as e:
            logger.error(e)

    def update_slope(self):
        pass

    async def publish_stream(self):
        if not self.book_stream:
            raise ValueError("No stream")

        # loop = asyncio.get_event_loop()
        async for book in self.book_stream:
            if book:
                self.parse_book(book)
            await asyncio.sleep(0)


PubsubProducer = Union[BalancePub, BinancePub, BTPub]
