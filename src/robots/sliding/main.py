import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, Optional

import simplejson as json  # type: ignore

import src.pubsub.pub as pub
from src.exchanges.base import ExchangeAPIClientBase
from src.robots.base import RobotBase
from src.stgs.sliding.config import SlidingWindowConfig
from src.robots.sliding.follower import FollowerWatcher
from src.robots.sliding.leader import LeaderWatcher
from src.robots.watchers import BalanceWatcher, BookWatcher
from src.monitoring import logger
from src.periodic import periodic
from src.stgs import BPS

getcontext().prec = 9

@dataclass
class TargetPrices:
    taker_buy: Optional[Decimal] = None
    taker_sell: Optional[Decimal] = None

    maker_buy: Optional[Decimal] = None
    maker_sell: Optional[Decimal] = None
@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig

    # Exchanges
    leader_api_client: ExchangeAPIClientBase
    follower_api_client: ExchangeAPIClientBase
    balance_watcher: BalanceWatcher
    balance_pubsub_key: str

    # Streams
    leader_book_stream: AsyncGenerator
    follower_book_stream: AsyncGenerator

    bridge_watcher: Optional[BookWatcher] = None
    bridge_pubsub_key: Optional[str] = None
  
    current_step: Decimal = Decimal("0")

    targets: TargetPrices = TargetPrices()

    def __post_init__(self) -> None:
        self.config_dict = self.config.dict()

        self.channnel = self.config.sha

        self.leader = LeaderWatcher(book_stream=self.leader_book_stream)

        self.follower = FollowerWatcher(
            config=self.config,
            exchange=self.follower_api_client,
            book_stream=self.follower_book_stream,
            balance_watcher=self.balance_watcher,
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
            periodic(
                self.follower.update_balances,
                self.config.sleep_seconds.update_balances / 4,
            ),
            periodic(
                self.follower.order_robot.cancel_all_open_orders,
                self.config.sleep_seconds.cancel_all_open_orders,
            ),
            periodic(self.broadcast_stats, self.config.sleep_seconds.broadcast_stats),
        ]

        await asyncio.gather(*coroutines)

    async def watch_leader(self) -> None:
        async for book in self.leader.book_generator():
            self.calculate_window(book)
            await self.should_transact()
            asyncio.create_task(self.clear_theo())

    async def clear_theo(self):
        # theo are valid for max 200ms 
        await asyncio.sleep(0.2) 
        self.theo_buy = None
        self.theo_sell = None

    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""
        if not book:
            return

        try:
            mid = self.leader_api_client.get_mid(book)

            if not mid:
                return

            if self.bridge_watcher:
                if self.bridge_watcher.quote:
                    mid *= self.bridge_watcher.quote
                else:
                    return

            self.update_step()

            step_size = self.config.input.step_bps * BPS * self.current_step * mid 
            
            mid -= step_size

            maker_credit = self.config.maker_credit_bps * BPS * mid
            taker_credit = self.config.taker_credit_bps * BPS * mid

            self.targets.maker_buy = mid - maker_credit
            self.targets.maker_sell = mid + maker_credit

            self.targets.taker_buy = mid - taker_credit
            self.targets.taker_sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)

    async def should_transact(self) -> None:
        if self.should_long() and self.theo_buy:
            await self.follower.long(self.theo_buy)

        if self.should_short() and self.theo_sell:
            await self.follower.short(self.theo_sell)

    def update_step(self):
        self.current_step = self.follower.pair.base.free / self.config.base_step_qty

    def should_long(self) -> bool:
        if not self.follower.best_seller:
            return False

        if not self.theo_buy:
            return False

        self.update_step()

        return (
            bool(self.follower.best_seller <= self.theo_buy) 
            and self.current_step <= self.config.input.max_step
        )

    def should_short(self) -> bool:
        if not self.follower.best_buyer:
            return False

        if not self.theo_sell:
            return False

        self.update_step()

        return (
            bool(self.follower.best_buyer >= self.theo_sell) 
            and self.current_step <= self.config.input.max_step
        )

    async def close(self) -> None:
        await self.follower.order_robot.cancel_all_open_orders()

    def create_stats_message(self) -> dict:
        stats = {
            "current time": datetime.now(),
            "start time": self.task_start_time,
            "orders": {
                "buy": {
                    "delivered": self.follower.order_robot.buy_orders_delivered,
                },
                "sell": {
                    "delivered": self.follower.order_robot.sell_orders_delivered,
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
            "binance": {
                "targets": self.targets,
                "last update": self.leader.theo_last_updated.time(),
                "books seen": self.leader.books_seen,
            },
            "btcturk": {
                "bid": self.follower.best_buyer,
                "ask": self.follower.best_seller,
                "last update": self.follower.bid_ask_last_updated.time(),
                "books seen": self.follower.books_seen,
            },
        }

        if self.bridge_watcher:
            stats["bridge"] = {
                "exchange": self.config.input.bridge_exchange,
                "quote": self.bridge_watcher.quote,
                "last update": self.bridge_watcher.last_updated,
            }

        stats["config"] = self.config_dict

        return stats

    async def broadcast_stats(self) -> None:

        message_dict = self.create_stats_message()

        message = json.dumps(message_dict, default=str)

        pub.publish_stats(self.channnel, message)
