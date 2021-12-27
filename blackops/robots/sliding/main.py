import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, Optional

import simplejson as json  # type: ignore

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.environment import debug
from blackops.exchanges.base import ExchangeBase
from blackops.robots.base import RobotBase
from blackops.robots.config import SlidingWindowConfig
from blackops.robots.sliding.bridge import BridgeWatcher
from blackops.robots.sliding.follower import FollowerWatcher
from blackops.robots.sliding.leader import LeaderWatcher
from blackops.util.logger import logger
from blackops.util.periodic import periodic

getcontext().prec = 6


@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig

    # Exchanges
    leader_exchange: ExchangeBase
    follower_exchange: ExchangeBase

    # Streams
    leader_book_stream: AsyncGenerator
    follower_book_stream: AsyncGenerator

    # Bridge
    bridge_exchange: Optional[ExchangeBase] = None
    bridge_stream: Optional[AsyncGenerator] = None

    # Realtime
    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell
    current_step: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        self.config_dict = self.config.dict()

        self.channnel = self.config.sha

        self.leader = LeaderWatcher(book_stream=self.leader_book_stream)

        self.follower = FollowerWatcher(
            config=self.config,
            exchange=self.follower_exchange,
            book_stream=self.follower_book_stream,
        )

        if self.config.use_bridge:
            self.bridge_watcher = BridgeWatcher(
                bridge_exchange=self.bridge_exchange, bridge_stream=self.bridge_stream
            )

    async def run(self) -> None:
        self.task_start_time = datetime.now()
        await self.run_streams()

    async def run_streams(self) -> None:
        logger.info(
            f"Start streams for {self.config.type.name} with config {self.config}"
        )

        coroutines: Any = [
            self.watch_leader(),
            self.follower.watch_books(),
            periodic(self.follower.update_balances, 0.72),
            periodic(self.follower.order_robot.watch_open_orders, 0.3),
            periodic(self.follower.order_robot.cancel_all_open_orders, 0.6),
            periodic(self.follower.update_pnl, 2),
            periodic(self.broadcast_stats, 0.8),
        ]  # is this ordering important ?
        if self.config.use_bridge:
            coroutines.append(self.bridge_watcher.watch_bridge())

        await asyncio.gather(*coroutines)

    async def watch_leader(self) -> None:
        async for book in self.leader.book_generator():
            self.calculate_window(book)
            await self.should_transact()

    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""
        if not book:
            return

        try:
            mid = self.leader_exchange.get_mid(book)

            if not mid:
                return

            if self.config.use_bridge:
                mid *= self.bridge_watcher.bridge_quote

            self.current_step = self.follower.pair.base.free / self.config.base_step_qty

            step_size = self.config.step_constant_k * self.current_step

            mid -= step_size

            self.theo_buy = mid - self.config.credit
            self.theo_sell = mid + self.config.credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)

    async def should_transact(self) -> None:
        if self.should_long():
            if self.theo_buy:
                await self.follower.long(self.theo_buy)

        if self.should_short():
            if self.theo_sell:
                await self.follower.short(self.theo_sell)

    def should_long(self) -> bool:
        if not self.follower.best_seller:
            return False

        if not self.theo_buy:
            return False

        return (
            bool(self.follower.best_seller <= self.theo_buy) and self.follower.can_buy()
        )

    def should_short(self) -> bool:
        if not self.follower.best_buyer:
            return False

        if not self.theo_sell:
            return False

        return (
            bool(self.follower.best_buyer >= self.theo_sell)
            and self.follower.can_sell()
        )

    async def close(self) -> None:
        await self.follower.order_robot.cancel_all_open_orders()

    def create_stats_message(self) -> dict:
        stats = {
            "current time": datetime.now().time(),
            "start time": self.task_start_time,
            "orders": {
                "note": "please also check the exchange",
                "buy": {
                    "delivered": self.follower.order_robot.buy_orders_delivered,
                    "open": len(self.follower.order_robot.open_buy_orders),
                    "realized": self.follower.order_robot.buy_orders_delivered
                    - len(self.follower.order_robot.open_buy_orders),
                },
                "sell": {
                    "delivered": self.follower.order_robot.sell_orders_delivered,
                    "open": len(self.follower.order_robot.open_sell_orders),
                    "realized": self.follower.order_robot.sell_orders_delivered
                    - len(self.follower.order_robot.open_sell_orders),
                },
            },
            "balances": {
                "start": {
                    "base": {
                        "free": self.follower.start_pair.base.free,
                        "locked": self.follower.start_pair.base.locked,
                    },
                    "quote": {
                        "free": self.follower.start_pair.quote.free,
                        "locked": self.follower.start_pair.quote.locked,
                    },
                },
                "current": {
                    "base": {
                        "free": self.follower.pair.base.free,
                        "locked": self.follower.pair.base.locked,
                    },
                    "quote": {
                        "free": self.follower.pair.quote.free,
                        "locked": self.follower.pair.quote.locked,
                    },
                    "step": self.current_step,
                },
                "pnl": self.follower.pnl,
                "max pnl ever seen": self.follower.max_pnl,
            },
            "binance": {
                "theo": {
                    "buy": self.theo_buy,
                    "sell": self.theo_sell,
                    "last_updated": self.leader.theo_last_updated.time(),
                },
                "bridge": {
                    "bridge_quote": self.bridge_watcher.bridge_quote,
                    "bridge_last_updated": self.bridge_watcher.bridge_last_updated,
                },
                "books seen": self.leader.books_seen,
            },
            "btcturk": {
                "bid": self.follower.best_buyer,
                "ask": self.follower.best_seller,
                "last_updated": self.follower.bid_ask_last_updated.time(),
                "books seen": self.follower.books_seen,
            },
            "config": self.config_dict,
        }

        return stats

    async def broadcast_stats(self) -> None:
        message = self.create_stats_message()

        message = json.dumps(message, default=str)

        pub.publish_stats(self.channnel, message)
