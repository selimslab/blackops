import asyncio
from contextlib import asynccontextmanager
import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Optional

import src.pubsub.pub as pub
from src.exchanges.base import ExchangeAPIClientBase
from src.stgs.sliding.config import SlidingWindowConfig
from src.robots.sliding.orders import OrderRobot
from src.robots.watchers import BalanceWatcher
from src.monitoring import logger


@dataclass
class FollowerWatcher:
    config: SlidingWindowConfig

    exchange: ExchangeAPIClientBase

    book_stream: AsyncGenerator
    balance_watcher: BalanceWatcher

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None

    bid_ask_last_updated: datetime = datetime.now()
    books_seen: int = 0

    start_balances_saved: bool = False

    def __post_init__(self):

        self.order_robot = OrderRobot(
            config=self.config, pair=self.config.create_pair(), exchange=self.exchange
        )
        self.channnel = self.config.sha

        self.pair = self.config.create_pair()

        self.start_pair = self.config.create_pair()


    async def watch_books(self) -> None:
        async for book in self.book_stream:
            self.update_follower_prices(book)
            self.books_seen += 1
            asyncio.create_task(self.clear_bid_ask())
            await asyncio.sleep(0)

    async def clear_bid_ask(self):
        # prices are valid for max 200ms 
        await asyncio.sleep(0.2) 

        self.best_buyer = None
        self.best_seller = None

    def update_follower_prices(self, book: dict) -> None:
        try:
            best_ask = self.exchange.get_best_ask(book)
            if best_ask:
                self.best_seller = best_ask

            best_bid = self.exchange.get_best_bid(book)
            if best_bid:
                self.best_buyer = best_bid

            self.bid_ask_last_updated = datetime.now()

        except Exception as e:
            msg = f"update_follower_prices: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)

    async def update_balances(self) -> None:
        try:
            res: Optional[dict] = self.balance_watcher.balances
            if not res:
                return

            balances = self.exchange.parse_account_balance(
                res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
            )

            base_balances: dict = balances[self.pair.base.symbol]
            self.pair.base.free = Decimal(base_balances["free"])
            self.pair.base.locked = Decimal(base_balances["locked"])

            quote_balances: dict = balances[self.pair.quote.symbol]
            self.pair.quote.free = Decimal(quote_balances["free"])
            self.pair.quote.locked = Decimal(quote_balances["locked"])

            if not self.start_balances_saved:
                self.start_pair = copy.deepcopy(self.pair)
                self.start_balances_saved = True

        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)
            raise e

    def can_buy(self, theo_buy) -> bool:
        return (
            bool(self.pair.quote.free) 
            and self.pair.quote.free >= theo_buy * self.config.base_step_qty
        )

    async def long(self, theo_buy: Decimal) -> Optional[dict]:
        if not self.can_buy(theo_buy):
            return None

        order_log = await self.order_robot.send_long_order(theo_buy)

        if order_log:
            logger.info(order_log)
            self.pair.base.free += self.config.base_step_qty
            return order_log

        return None

    async def short(self, theo_sell: Decimal) -> Optional[dict]:
        qty = float(self.config.base_step_qty)
        if self.pair.base.free < qty:
            qty = float(self.pair.base.free) * 0.98

        order_log = await self.order_robot.send_short_order(theo_sell, qty)
        if order_log:
            logger.info(order_log)
            # If we deliver order, we reflect it in balance until we read the current balance
            self.pair.base.free -= self.config.base_step_qty
            return order_log
        return None