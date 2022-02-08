import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Optional, Union

import numpy as np
import talib

import src.streams.bn as bn_streams
import src.streams.btcturk as btc_streams
from src.domain.models import BPS, DECIMAL_2, Asset, AssetSymbol, Book
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.numberops import RollingMean
from src.periodic import periodic
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
            self.update_balances(res)
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

    book: Book = field(default_factory=Book)

    book_stream: Optional[AsyncGenerator] = None

    def __post_init__(self):
        self.book_stream = btc_streams.create_book_stream(self.symbol)

    async def run(self):
        await self.publish_stream()

    def parse_book(self, book):
        try:
            ask = self.api_client.get_best_ask(book)
            bid = self.api_client.get_best_bid(book)

            if ask and bid:
                self.book.ask = ask
                self.book.bid = bid
                self.book.mid = (ask + bid) / DECIMAL_2
                self.book.seen += 1
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
class SlopeThresholds:
    up: float = 6
    slope_risk_start: float = 3


@dataclass
class Slope:
    up: bool = False

    thresholds: SlopeThresholds = field(default_factory=SlopeThresholds)

    former: float = 0
    latter: float = 0
    diff: float = 0
    diff_bps: float = 0
    risk_level: float = 0


@dataclass
class BinancePub(PublisherBase):

    symbol: str

    api_client: ExchangeAPIClientBase

    book: Book = field(default_factory=Book)

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
        await asyncio.gather(self.publish_stream(), periodic(self.publish_klines, 3))

    def parse_book(self, book):
        try:
            if "data" in book:
                ask = Decimal(book["data"]["a"])
                bid = Decimal(book["data"]["b"])

                if ask and bid and (ask != self.book.ask or bid != self.book.bid):

                    self.book.ask = ask
                    self.book.bid = bid

                    mid = (ask + bid) / DECIMAL_2

                    self.spread_bps = (ask - bid) / mid / BPS

                    # self.ma_small.add(mid)
                    # self.ma_mid.add(mid)
                    # self.ma_large.add(mid)

                    if mid != self.book.mid:
                        # self.micro_ma_ok = bool(
                        #     self.ma_small.get_average()
                        #     > self.ma_mid.get_average()
                        #     > self.ma_large.get_average()
                        # )
                        self.book.mid = mid
                        self.book.seen += 1
        except Exception as e:
            logger.error(e)

    def ema(self, close: list, period: int):
        n = len(close)
        ans = []
        end = period
        old_ema = statistics.mean(close[:end])

        while end <= n:
            k = 2.0 / (period + 1)
            ema = close[end - 1] * k + old_ema * (1 - k)
            ans.append(ema)
            old_ema = ema
            end += 1

        return ans

    async def publish_klines(self):
        try:
            klines = await bn_streams.get_klines(self.symbol, interval="1m", limit=6)
            if klines:
                kline_closes = [float(k[4]) for k in klines]
                closes = np.asarray(kline_closes)
                ema = talib.EMA(closes, timeperiod=5)
                self.slope.former, self.slope.latter = ema[-2:]

                # self.slope.former, self.slope.latter = self.ema(
                #     kline_closes, 5
                # )

                # kline_closes[:5], kline_closes[1:]

                # former = statistics.mean(kline_closes[:5])
                # latter = statistics.mean(kline_closes[1:])
                self.slope.diff = self.slope.latter - self.slope.former
                diff_bps = self.slope.diff / self.slope.latter * 10000

                self.slope.up = bool(
                    diff_bps >= self.slope.thresholds.up  # and second_dt_up
                )

                risk = self.slope.thresholds.slope_risk_start - diff_bps

                # risk cant be > 7
                risk = min(12, risk)
                # risk cant be < 0
                risk = max(0, risk)

                self.slope.risk_level = risk

                self.slope.diff_bps = diff_bps

        except Exception as e:
            logger.error(e, exc_info=True)

    async def publish_stream(self):
        if not self.book_stream:
            raise ValueError("No stream")

        # loop = asyncio.get_event_loop()
        async for book in self.book_stream:
            if book:
                self.parse_book(book)
            await asyncio.sleep(0)


PubsubProducer = Union[BalancePub, BinancePub, BTPub]
