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
from blackops.robots.bridge import BridgeWatcher
from blackops.robots.config import SlidingWindowConfig
from blackops.robots.follower import FollowerWatcher
from blackops.robots.leader import LeaderWatcher
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

    def __post_init__(self):
        pair = AssetPair(
            Asset(symbol=self.config.base), Asset(symbol=self.config.quote)
        )

        self.config_dict = self.config.dict()

        self.channnel = self.config.sha

        self.leader = LeaderWatcher(book_stream=self.leader_book_stream)

        self.follower = FollowerWatcher(
            config=self.config,
            pair=pair,
            exchange=self.follower_exchange,
            book_stream=self.follower_book_stream,
        )

        if self.config.use_bridge:
            self.bridge_watcher = BridgeWatcher(
                bridge_exchange=self.follower_exchange, bridge_stream=self.bridge_stream
            )

    async def run(self):
        self.task_start_time = datetime.now()
        await self.run_streams()

    async def run_streams(self):
        logger.info(
            f"Start streams for {self.config.type.name} with config {self.config}"
        )

        coroutines: Any = [
            self.watch_leader(),
            self.follower.watch_follower(),
            periodic(self.follower.update_balances, 0.72),
            periodic(self.follower.order_robot.watch_open_orders, 0.3),
            periodic(self.follower.order_robot.cancel_all_open_orders, 0.6),
            periodic(self.follower.update_pnl, 1),
            periodic(self.broadcast_stats, 0.5),
        ]  # is this ordering important ?
        if self.config.use_bridge:
            coroutines.append(self.bridge_watcher.watch_bridge())

        await asyncio.gather(*coroutines)

    async def watch_leader(self):
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

    async def should_transact(self):
        if self.should_long():
            if self.theo_buy:
                await self.follower.long(self.theo_buy)

        if self.should_short():
            if self.theo_sell:
                await self.follower.short(self.theo_sell)

    def should_long(self):
        # we don't enforce max_usable_quote_amount_y too strict
        # we assume no deposits to quote during the task run
        return (
            self.follower.best_seller
            and self.theo_buy
            and self.follower.best_seller <= self.theo_buy
            and self.follower.can_buy()
            #  self.follower.pair.quote.free >= self.follower.best_seller * self.config.base_step_qty
        )

    def should_short(self):
        #  act only when you are ahead
        return (
            self.follower.best_buyer
            and self.theo_sell
            and self.follower.best_buyer >= self.theo_sell
            and self.follower.can_sell()
        )

    def get_orders(self):
        return self.follower.order_robot.get_orders()

    async def close(self):
        await self.follower.order_robot.cancel_all_open_orders()

    def create_stats_message(self):
        stats = {
            "current time": datetime.now().time(),
            "start time": self.task_start_time,
            "balances": {
                "start": {
                    "base": self.follower.start_base_total,
                    "quote": self.follower.start_quote_total,
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
                    "note": "balances are approximate since orders take time ",
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
            "orders": {
                "open_buy_orders": self.follower.order_robot.open_buy_orders,
                "open_sell_orders": self.follower.order_robot.open_sell_orders,
                "buy_orders": self.follower.order_robot.buy_orders,
                "sell_orders": self.follower.order_robot.sell_orders,
            },
            "config": self.config_dict,
        }

        return stats

    async def broadcast_stats(self):
        message = self.create_stats_message()

        message = json.dumps(message, default=str)

        pub.publish_stats(self.channnel, message)
