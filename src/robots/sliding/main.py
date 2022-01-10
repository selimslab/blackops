import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, Optional

import src.pubsub.pub as pub
from src.monitoring import logger
from src.numberops import one_bps_higher, one_bps_lower, round_decimal
from src.periodic import SingleTaskContext, periodic
from src.robots.base import RobotBase
from src.robots.pubs import BalancePub, BookPub
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

    leader_station: BookPub
    follower_station: BookPub
    balance_station: BalancePub
    bridge_station: Optional[BookPub] = None

    current_step: Decimal = Decimal("0")

    market_prices: Targets = Targets()
    targets: Targets = Targets()

    fresh_price_task: SingleTaskContext = SingleTaskContext()

    def __post_init__(self) -> None:
        self.config_dict = self.config.dict()

        self.follower = MarketWatcher(
            config=self.config,
            book_station=self.follower_station,
            balance_station=self.balance_station,
        )

    async def run(self) -> None:
        self.task_start_time = datetime.now()
        await self.run_streams()

    async def run_streams(self) -> None:
        logger.info(
            f"Start streams for {self.config.type.name} with config {self.config}"
        )

        aws: Any = [
            self.watch_leader_books(),
            self.follower.watch_books(),
            periodic(
                self.follower.update_balances,
                self.config.sleep_seconds.update_balances / 6,
            ),
            periodic(
                self.follower.order_api.cancel_all_open_orders,
                self.config.sleep_seconds.cancel_all_open_orders,
            ),
        ]

        if self.bridge_station:
            aws.append(self.watch_bridge_books())

        await asyncio.gather(*aws)

    async def watch_leader_books(self) -> None:
        async for book in self.leader_station.stream:
            await self.decide(book)

    async def decide(self, book) -> None:
        async with self.fresh_price_task.refresh_task(self.clear_targets):
            self.calculate_window(book)
            self.leader_station.last_updated = datetime.now()
            await self.should_transact()

    async def watch_bridge_books(self) -> None:
        if not self.bridge_station:
            raise Exception("no bridge_station")

        async for book in self.bridge_station.stream:
            if book:
                self.bridge_station.last_updated = datetime.now()
                self.targets.bridge = self.bridge_station.api_client.get_mid(book)

    async def clear_targets(self):
        # theo are valid for max 200ms
        await asyncio.sleep(self.config.sleep_seconds.clear_prices)
        self.targets.maker.buy = None
        self.targets.maker.sell = None

        self.targets.taker.buy = None
        self.targets.taker.sell = None

    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""
        if not book:
            return

        try:
            mid = self.leader_station.api_client.get_mid(book)

            if not mid:
                return

            if self.targets.bridge:
                mid *= self.targets.bridge

            self.update_step()

            step_size = self.config.credits.step * mid * self.current_step

            mid -= step_size

            maker_credit = self.config.credits.maker * mid
            self.targets.maker.buy = mid - maker_credit
            self.targets.maker.sell = mid + maker_credit

            taker_credit = self.config.credits.taker * mid
            self.targets.taker.buy = mid - taker_credit
            self.targets.taker.sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            pub.publish_error(message=msg)

    async def should_transact(self) -> None:
        if self.can_short():
            price = self.get_short_price()
            if price:
                await self.follower.short(price)

        if self.can_long():
            price = self.get_long_price()
            if price:
                await self.follower.long(price)

    def update_step(self):
        self.current_step = self.follower.pair.base.free / self.config.base_step_qty

    # def update_base_qty(self, mid):
    #     self.config.base_step_qty = round_decimal(
    #         self.config.input.quote_step_qty / mid
    #     )

    def can_long(self) -> bool:
        self.update_step()

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

    def can_short(self) -> bool:
        self.update_step()

        prices_ok = bool(
            self.follower.prices.bid
            and self.targets.taker.sell
            and self.targets.maker.sell
        )
        balance_ok = self.follower.pair.base.free >= self.config.base_step_qty

        return prices_ok and balance_ok

    def get_short_price(self) -> Optional[Decimal]:
        """
        if targets.maker.sell <= bid < targets.taker.sell
            sell order at one_bps_higher(bid)
        if bid >= targets.taker.sell:
            sell order at bid
        """
        if not self.can_short():
            return None

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
                    "last update": self.leader_station.last_updated.time(),
                    "books seen": self.leader_station.books_seen,
                },
                "btcturk": {
                    "bid": self.follower.prices.bid,
                    "ask": self.follower.prices.ask,
                    "last update": self.follower_station.last_updated.time(),
                    "books seen": self.follower_station.books_seen,
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

        if self.bridge_station:
            stats["bridge"] = {
                "exchange": self.config.input.bridge_exchange,
                "quote": self.targets.bridge,
                "last update": self.bridge_station.last_updated,
            }

        stats["config"] = self.config_dict

        return stats
