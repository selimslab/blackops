import asyncio
import decimal
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import src.pubsub.log_pub as log_pub
from src.domain import BPS, maker_fee_bps, taker_fee_bps
from src.environment import sleep_seconds
from src.monitoring import logger
from src.periodic import StopwatchAPI, periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.market import MarketWatcher
from src.stgs.sliding.config import LeaderFollowerConfig


@dataclass
class TargetPrices:
    buy: Optional[Decimal] = None
    sell: Optional[Decimal] = None


@dataclass
class Window:
    mid: Optional[Decimal] = None
    bridge: Optional[Decimal] = None
    # maker: TargetPrices = field(default_factory=TargetPrices)
    taker: TargetPrices = field(default_factory=TargetPrices)


@dataclass
class Stopwatches:
    leader: StopwatchAPI = field(default_factory=StopwatchAPI)
    bridge: StopwatchAPI = field(default_factory=StopwatchAPI)


@dataclass
class Credits:
    maker: Decimal = Decimal(0)
    taker: Decimal = Decimal(0)
    step: Decimal = Decimal(0)


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    current_step: Decimal = Decimal("0")

    targets: Window = field(default_factory=Window)

    stopwatches: Stopwatches = field(default_factory=Stopwatches)

    start_time: datetime = field(default_factory=lambda: datetime.now())

    credits: Credits = Credits()

    def __post_init__(self) -> None:
        self.set_credits()
        self.follower = MarketWatcher(
            config=self.config,
            book_pub=self.follower_pub,
            balance_pub=self.balance_pub,
        )

    def set_credits(self):
        try:
            self.credits.maker = (
                (maker_fee_bps + taker_fee_bps) / Decimal(2)
            ) + self.config.margin_bps
            self.credits.taker = taker_fee_bps + self.config.margin_bps
            self.credits.step = self.credits.taker / self.config.max_step
        except Exception as e:
            logger.error(e)
            raise e

    async def run(self) -> None:
        logger.info(f"Starting {self.config.sha}..")
        await self.run_streams()

    async def run_streams(self) -> None:
        aws: Any = [
            self.consume_leader_pub(),
            self.follower.consume_pub(),
            periodic(
                self.follower.update_balances,
                sleep_seconds.poll_balance_update,
            ),
            periodic(
                self.follower.order_api.refresh_open_orders,
                sleep_seconds.refresh_open_orders,
            ),
            periodic(
                self.follower.order_api.cancel_open_orders,
                sleep_seconds.cancel_open_orders,
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
                self.targets.bridge = mid

    def clear_targets(self):
        self.targets = Window()

    def clear_bridge(self):
        self.targets.bridge = None

    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            await self.decide(book)

    async def decide(self, book) -> None:
        mid = self.get_window_mid(book)
        if mid:
            async with self.stopwatches.leader.stopwatch(
                self.clear_targets, sleep_seconds.clear_prices
            ):
                self.update_window(mid)

            await self.should_transact()

    async def should_transact(self) -> None:

        taker_sell = self.get_short_price_taker()
        if taker_sell:
            await self.follower.short(taker_sell, self.config.base_step_qty)

        taker_buy = self.get_long_price_taker()
        if taker_buy and self.current_step <= self.config.max_step:
            await self.follower.long(taker_buy, self.config.base_step_qty)

    def update_step(self):
        self.current_step = self.follower.pair.base.free / self.config.base_step_qty

    def get_window_mid(self, book: dict) -> Optional[Decimal]:
        if not book:
            return None
        try:
            leader_mid = self.leader_pub.api_client.get_mid(book)

            self.targets.mid = leader_mid
            if not leader_mid:
                return None

            if self.config.input.use_bridge:
                if self.targets.bridge:
                    return leader_mid * self.targets.bridge
                return None
            else:
                return leader_mid

        except Exception as e:
            msg = f"get_window_mid: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            return None

    def update_window(self, mid: Decimal) -> None:

        try:
            self.update_step()

            slide_down = self.credits.step * self.current_step * mid * BPS

            mid -= slide_down

            taker_credit = self.credits.taker * mid * BPS
            self.targets.taker.buy = mid - taker_credit
            self.targets.taker.sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    def get_precise_price(self, price: Decimal, reference: Decimal) -> Decimal:
        return price.quantize(reference, rounding=decimal.ROUND_DOWN)

    def get_long_price_taker(self) -> Optional[Decimal]:
        ask = self.follower.prices.ask

        if ask and self.targets.taker.buy and ask <= self.targets.taker.buy:
            return self.get_precise_price(self.targets.taker.buy, ask)

        return None

    def get_short_price_taker(self) -> Optional[Decimal]:
        bid = self.follower.prices.bid

        if bid and self.targets.taker.sell and bid >= self.targets.taker.sell:
            return self.get_precise_price(self.targets.taker.sell, bid)
        return None

    async def close(self) -> None:
        await self.follower.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "credits": asdict(self.credits),
            "order stats": asdict(self.follower.order_api.stats),
            "open orders": list(self.follower.order_api.open_order_ids),
            "cancelled orders": list(self.follower.order_api.cancelled),
            "open_orders_fresh": self.follower.order_api.open_orders_fresh,
            "targets": asdict(self.targets),
            "market": asdict(self.follower.prices),
            "binance": {
                "last update": self.leader_pub.last_updated.time(),
                "books seen": self.leader_pub.books_seen,
            },
            "btc": {
                "last update": self.follower_pub.last_updated.time(),
                "books seen": self.follower_pub.books_seen,
            },
        }
