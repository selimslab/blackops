import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, Optional

import src.pubsub.log_pub as log_pub
from src.domain import BPS
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import one_bps_higher, one_bps_lower, round_decimal
from src.periodic import SingleTaskContext, periodic
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
    maker: TargetPrices = TargetPrices()
    taker: TargetPrices = TargetPrices()
    bridge: Optional[Decimal] = None


@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    current_step: Decimal = Decimal("0")

    market_prices: Targets = Targets()
    targets: Targets = Targets()

    fresh_price_task: SingleTaskContext = SingleTaskContext()

    def __post_init__(self) -> None:
        self.follower = MarketWatcher(
            config=self.config,
            book_pub=self.follower_pub,
            balance_pub=self.balance_pub,
        )

    async def run(self) -> None:
        self.task_start_time = datetime.now()
        await self.run_streams()

    async def run_streams(self) -> None:
        logger.info(
            f"Start streams for {self.config.type.name} with config {self.config}"
        )

        aws: Any = [
            self.consume_leader_pub(),
            self.follower.consume_pub(),
            periodic(
                self.follower.update_balances,
                sleep_seconds.update_balances / 6,
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
            self.targets.bridge = self.bridge_pub.api_client.get_mid(book)

    async def clear_targets(self):
        await asyncio.sleep(sleep_seconds.clear_prices)
        self.targets = Targets()

    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            await self.decide(book)

    async def decide(self, book) -> None:
        async with self.fresh_price_task.refresh_task(self.clear_targets):
            self.calculate_window(book)
            await self.should_transact()

    async def should_transact(self) -> None:
        sell_price = self.get_short_price()
        if sell_price:
            await self.follower.short(sell_price)

        if self.can_long():
            buy_price = self.get_long_price()
            if buy_price:
                await self.follower.long(buy_price)

    def update_step(self):
        self.current_step = self.follower.pair.base.free / self.config.base_step_qty

    def calculate_window(self, book: dict) -> None:
        if not book:
            return

        try:
            mid = self.leader_pub.api_client.get_mid(book)
            if not mid:
                return

            if self.config.input.use_bridge:
                if self.targets.bridge:
                    mid *= self.targets.bridge
                else:
                    self.targets = Targets()
                    return None

            self.update_step()

            slide_down = self.config.credits.step * self.current_step * mid * BPS

            mid -= slide_down

            maker_credit = self.config.credits.maker * mid * BPS
            self.targets.maker.buy = mid - maker_credit
            self.targets.maker.sell = mid + maker_credit

            taker_credit = self.config.credits.taker * mid * BPS
            self.targets.taker.buy = mid - taker_credit
            self.targets.taker.sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    def can_long(self) -> bool:
        prices_ok = bool(
            self.follower.prices.ask
            and self.targets.taker.buy
            and self.targets.maker.buy
        )
        step_ok = self.current_step <= self.config.input.max_step

        return prices_ok and step_ok

    def get_long_price(self) -> Optional[Decimal]:
        """
        if targets.taker.buy < ask <= targets.maker.buy
            buy order at one_bps_lower(ask)
        if ask <= targets.taker.buy:
            buy order at taker.buy
        """
        if not self.can_long():
            return None

        ask = self.follower.prices.ask
        if (
            ask
            and self.targets.taker.buy
            and self.targets.maker.buy
            and self.targets.taker.buy < ask <= self.targets.maker.buy
        ):
            return one_bps_lower(ask)
        elif ask and self.targets.taker.buy and ask <= self.targets.taker.buy:
            return self.targets.taker.buy
        else:
            return None

    def get_short_price(self) -> Optional[Decimal]:
        """
        if targets.maker.sell <= bid < targets.taker.sell
            sell order at one_bps_higher(bid)
        if bid >= targets.taker.sell:
            sell order at bid
        """

        bid = self.follower.prices.bid

        if (
            bid
            and self.targets.taker.sell
            and self.targets.maker.sell
            and self.targets.maker.sell <= bid < self.targets.taker.sell
        ):
            return one_bps_higher(bid)
        elif bid and self.targets.taker.sell and bid >= self.targets.taker.sell:
            return bid
        else:
            return None

    async def close(self) -> None:
        await self.follower.order_api.cancel_all_open_orders()

    def create_stats_message(self) -> dict:
        stats = {
            "pair": self.follower.pair.base.symbol + self.follower.pair.quote.symbol,
            "current time": datetime.now(),
            "start time": self.task_start_time,
            "orders delivered": {
                "buy": self.follower.order_api.orders_delivered.buy,
                "sell": self.follower.order_api.orders_delivered.sell,
            },
            "prices": {
                "binance": {
                    "targets": asdict(self.targets),
                    "last update": self.leader_pub.last_updated.time(),
                    "books seen": self.leader_pub.books_seen,
                },
                "btcturk": {
                    "bid": self.follower.prices.bid,
                    "ask": self.follower.prices.ask,
                    "last update": self.follower_pub.last_updated.time(),
                    "books seen": self.follower_pub.books_seen,
                },
            },
            "balances": {
                "step": self.current_step,
                "start": {
                    self.follower.pair.base.symbol: {
                        "free": self.follower.start_pair.base.free,
                        "locked": self.follower.start_pair.base.locked,
                    },
                    self.follower.pair.quote.symbol: {
                        "free": self.follower.start_pair.quote.free,
                        "locked": self.follower.start_pair.quote.locked,
                    },
                },
                "current": {
                    self.follower.pair.base.symbol: {
                        "free": self.follower.pair.base.free,
                        "locked": self.follower.pair.base.locked,
                    },
                    self.follower.pair.quote.symbol: {
                        "free": self.follower.pair.quote.free,
                        "locked": self.follower.pair.quote.locked,
                    },
                },
            },
        }

        if self.bridge_pub:
            stats["bridge"] = {
                "exchange": self.config.input.bridge_exchange,
                "quote": self.targets.bridge,
                "last update": self.bridge_pub.last_updated,
            }

        return stats
