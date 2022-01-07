import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, Optional

import src.pubsub.pub as pub
from src.exchanges.base import ExchangeAPIClientBase
from src.robots.base import RobotBase
from src.stgs.sliding.config import SlidingWindowConfig
from src.robots.sliding.follower import FollowerWatcher
from src.robots.sliding.leader import LeaderWatcher
from src.robots.watchers import BalanceWatcher, BookWatcher
from src.monitoring import logger
from src.periodic import periodic
from src.domain import BPS
from src.numberops import one_bps_lower

getcontext().prec = 9


@dataclass
class TargetPrices:
    buy: Optional[Decimal] = None
    sell : Optional[Decimal] = None


@dataclass
class Targets:
    maker : TargetPrices = TargetPrices()
    taker : TargetPrices = TargetPrices()




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

    targets: Targets = Targets()

    clear_task = None

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
                self.config.sleep_seconds.update_balances / 6,
            ),
            periodic(
                self.follower.order_robot.cancel_all_open_orders,
                self.config.sleep_seconds.cancel_all_open_orders,
            )
        ]

        await asyncio.gather(*coroutines)

    async def watch_leader(self) -> None:
        async for book in self.leader.book_generator():
            self.calculate_window(book)
            await self.should_transact()
            if self.clear_task:
                self.clear_task.cancel()
            self.clear_task = asyncio.create_task(self.clear_targets())

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
            mid = self.leader_api_client.get_mid(book)

            if not mid:
                return

            if self.bridge_watcher:
                if self.bridge_watcher.quote:
                    mid *= self.bridge_watcher.quote
                else:
                    return

            self.update_step()

            step_size = self.config.input.step_bps * BPS * mid * self.current_step  

            mid -= step_size

            maker_credit = self.config.maker_credit_bps * BPS * mid
            taker_credit = self.config.taker_credit_bps * BPS * mid

            self.targets.maker.buy = mid - maker_credit
            self.targets.maker.sell = mid + maker_credit

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

    def can_long(self) -> bool:
        self.update_step()

        have_all_prices = bool(self.follower.best_seller and self.targets.taker.buy and self.targets.maker.buy)
        step_ok = self.current_step <= self.config.input.max_step
        ready = have_all_prices and step_ok
        return ready

    def get_long_price(self) -> Optional[Decimal]:

        if not self.can_long():
            return None 

        best_seller = self.follower.best_seller
        if self.targets.taker.buy < best_seller < self.targets.maker.buy:  # type: ignore
            return one_bps_lower(best_seller)  # type: ignore
        elif best_seller <= self.targets.taker.buy:  # type: ignore
            return self.targets.taker.buy

        return None

    def can_short(self) -> bool:
        self.update_step()

        have_all_prices = bool(self.follower.best_buyer and self.targets.taker.sell and self.targets.maker.sell)
        have_balance = self.follower.pair.base.free >= self.config.base_step_qty
        ready = have_all_prices and have_balance
        return ready

    def get_short_price(self) -> Optional[Decimal]:
        if not self.can_short():
            return None

        best_buyer = self.follower.best_buyer

        if self.targets.taker.sell < best_buyer < self.targets.maker.sell:  # type: ignore
            return one_bps_lower(best_buyer)  # type: ignore
        elif best_buyer <= self.targets.taker.sell:  # type: ignore
            return self.targets.taker.sell

        return None

    async def close(self) -> None:
        await self.follower.order_robot.cancel_all_open_orders()

    def create_stats_message(self) -> dict:
        stats = {
            "pair": self.follower.pair.base.symbol +self.follower.pair.quote.symbol,
            "current time": datetime.now(),
            "start time": self.task_start_time,
            "orders delivered": {
                "buy": self.follower.order_robot.buy_orders_delivered,
                "sell": self.follower.order_robot.sell_orders_delivered,
            },
            "prices": {
                "binance": {
                    "targets": asdict(self.targets),
                    "last update": self.leader.theo_last_updated.time(),
                    "books seen": self.leader.books_seen,
                },
                "btcturk": {
                    "bid": self.follower.best_buyer,
                    "ask": self.follower.best_seller,
                    "last update": self.follower.bid_ask_last_updated.time(),
                    "books seen": self.follower.books_seen,
                }
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

        if self.bridge_watcher:
            stats["bridge"] = {
                "exchange": self.config.input.bridge_exchange,
                "quote": self.bridge_watcher.quote,
                "last update": self.bridge_watcher.last_updated,
            }

        stats["config"] = self.config_dict

        return stats
