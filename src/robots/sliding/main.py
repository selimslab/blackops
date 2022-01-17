import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, Optional

import src.pubsub.log_pub as log_pub
from src.domain import BPS
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import one_bps_higher, one_bps_lower, round_decimal_half_up
from src.periodic import StopwatchContext, periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.market import MarketWatcher
from src.stgs.sliding.config import SlidingWindowConfig

getcontext().prec = 9


@dataclass
class TargetPrices:
    buy: Optional[Decimal] = None
    sell: Optional[Decimal] = None


@dataclass
class Targets:
    maker: TargetPrices = field(default_factory=TargetPrices)
    taker: TargetPrices = field(default_factory=TargetPrices)
    bridge: Optional[Decimal] = None


@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    current_step: Decimal = Decimal("0")

    targets: Targets = field(default_factory=Targets)

    stopwatch_api: StopwatchContext = field(default_factory=StopwatchContext)

    start_time: datetime = field(default_factory=lambda: datetime.now())

    def __post_init__(self) -> None:
        self.follower = MarketWatcher(
            config=self.config,
            book_pub=self.follower_pub,
            balance_pub=self.balance_pub,
        )

    async def run(self) -> None:
        logger.info(f"Starting {self.config.sha}..")
        await self.run_streams()

    async def run_streams(self) -> None:
        aws: Any = [
            self.consume_leader_pub(),
            self.follower.consume_pub(),
            periodic(
                self.follower.update_balances,
                sleep_seconds.update_balances / 8,
            ),
            periodic(
                self.follower.order_api.cancel_all_open_orders,
                sleep_seconds.cancel_all_open_orders,
            ),
        ]

        if self.bridge_pub:
            aws.append(self.consume_bridge_pub())

        await asyncio.gather(*aws)

    async def consume_bridge_pub(self) -> None:
        if not self.bridge_pub:
            raise Exception("no bridge_pub")

        gen = create_book_consumer_generator(self.bridge_pub)
        async for book in gen:
            mid = self.bridge_pub.api_client.get_mid(book)
            if mid:
                async with self.stopwatch_api.stopwatch(
                    self.clear_bridge, sleep_seconds.clear_prices
                ):
                    self.targets.bridge = mid

    def clear_targets(self):
        self.targets = Targets()

    def clear_bridge(self):
        self.targets.bridge = None

    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            await self.decide(book)

    async def decide(self, book) -> None:
        mid = self.get_window_mid(book)
        if mid:
            async with self.stopwatch_api.stopwatch(
                self.clear_targets, sleep_seconds.clear_prices
            ):
                self.update_window(mid)

            await self.should_transact()

    async def should_transact(self) -> None:
        # maker_sell = self.get_short_price_maker()
        # if maker_sell:
        #     await self.follower.short(maker_sell)

        taker_sell = self.get_short_price_taker()
        if taker_sell:
            await self.follower.short(taker_sell)

        taker_buy = self.get_long_price_taker()
        if taker_buy and self.current_step <= self.config.input.max_step:
            await self.follower.long(taker_buy)

            # maker_buy = self.get_long_price_maker()
            # if maker_buy:
            #     await self.follower.long(maker_buy)

    def update_step(self):
        self.current_step = self.follower.pair.base.free / self.config.base_step_qty

    def get_window_mid(self, book: dict) -> Optional[Decimal]:
        if not book:
            return None
        try:
            mid = self.leader_pub.api_client.get_mid(book)
            if not mid:
                return None

            if self.config.input.use_bridge:
                if self.targets.bridge:
                    mid *= self.targets.bridge
                    return mid

            return None

        except Exception as e:
            msg = f"get_window_mid: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            return None

    def update_window(self, mid: Decimal) -> None:

        try:
            self.update_step()

            slide_down = self.config.credits.step * self.current_step * mid * BPS

            mid -= slide_down

            # maker_credit = self.config.credits.maker * mid * BPS
            # self.targets.maker.buy = mid - maker_credit
            # self.targets.maker.sell = mid + maker_credit

            taker_credit = self.config.credits.taker * mid * BPS
            self.targets.taker.buy = mid - taker_credit
            self.targets.taker.sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    def get_long_price_taker(self) -> Optional[Decimal]:
        """
        if targets.taker.buy < ask <= targets.maker.buy
            buy order at one_bps_lower(ask)
        if ask <= targets.taker.buy:
            buy order at taker.buy
        """
        ask = self.follower.prices.ask

        if ask and self.targets.taker.buy and ask <= self.targets.taker.buy:
            return self.targets.taker.buy

        return None

    def get_short_price_taker(self) -> Optional[Decimal]:
        """
        if targets.maker.sell <= bid < targets.taker.sell
            sell order at one_bps_higher(bid)
        if bid >= targets.taker.sell:
            sell order at bid
        """
        bid = self.follower.prices.bid

        if bid and self.targets.taker.sell and bid >= self.targets.taker.sell:
            return bid
        return None

    async def close(self) -> None:
        await self.follower.order_api.cancel_all_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "orders_delivered": asdict(self.follower.order_api.orders_delivered),
            "orders_tried": asdict(self.follower.order_api.orders_tried),
            "targets": asdict(self.targets),
            "btc": {
                "bid": self.follower.prices.bid,
                "ask": self.follower.prices.ask,
                "last update": self.follower_pub.last_updated.time(),
                "books seen": self.follower_pub.books_seen,
            },
            "binance": {
                "last update": self.leader_pub.last_updated.time(),
                "books seen": self.leader_pub.books_seen,
            },
        }

    # def get_long_price_maker(self) -> Optional[Decimal]:

    #     ask = self.follower.prices.ask

    #     if (
    #         ask
    #         and self.targets.taker.buy
    #         and self.targets.maker.buy
    #         and self.targets.taker.buy < ask <= self.targets.maker.buy
    #     ):
    #         return one_bps_lower(ask)

    #     return None

    # def get_short_price_maker(self) -> Optional[Decimal]:
    #     bid = self.follower.prices.bid

    #     if (
    #         bid
    #         and self.targets.taker.sell
    #         and self.targets.maker.sell
    #         and self.targets.maker.sell <= bid < self.targets.taker.sell
    #     ):
    #         return one_bps_higher(bid)

    #     return None
