import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Optional

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.robots.config import SlidingWindowConfig
from blackops.robots.sliding.orders import OrderRobot
from blackops.util.logger import logger


@dataclass
class FollowerWatcher:
    exchange: ExchangeBase
    config: SlidingWindowConfig
    pair: AssetPair
    book_stream: AsyncGenerator

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None

    bid_ask_last_updated: datetime = datetime.now()
    books_seen: int = 0

    # we don't enforce max_usable_quote_amount_y too strict
    # we assume no deposits to quote during the task run
    total_used_quote_amount: Decimal = Decimal("0")
    start_balances_saved: bool = False

    pnl: Decimal = Decimal("0")
    max_pnl: Decimal = Decimal("0")

    def __post_init__(self):
        self.order_robot = OrderRobot(
            config=self.config, pair=self.pair, exchange=self.exchange
        )
        self.channnel = self.config.sha
        self.start_pair = copy.deepcopy(self.pair)

    async def watch_books(self) -> None:
        async for book in self.book_stream:
            if book:
                self.update_follower_prices(book)
                self.books_seen += 1
            await asyncio.sleep(0)

    def update_follower_prices(self, book: dict) -> None:
        if not book:
            return
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
            res: Optional[dict] = await self.exchange.get_account_balance()
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

            self.update_used_quote()

        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)
            raise e

    def can_sell(self) -> bool:
        return (
            bool(self.pair.base.free)
            and self.pair.base.free >= self.config.base_step_qty
        )

    def can_buy(self) -> bool:
        approximate_buy_cost = self.approximate_buy_cost()
        enough_free_balance = (
            bool(self.pair.quote.free) and self.pair.quote.free >= approximate_buy_cost
        )
        will_not_exceed_the_spending_limit = (
            self.total_used_quote_amount + approximate_buy_cost
            <= self.config.max_usable_quote_amount_y
        )
        return enough_free_balance and will_not_exceed_the_spending_limit

    async def long(self, theo_buy: Decimal) -> Optional[dict]:
        if not self.best_seller:
            return None

        order_log = await self.order_robot.send_long_order(self.best_seller, theo_buy)

        if order_log:
            self.pair.base.free += self.config.base_step_qty
            self.pair.quote.free -= self.approximate_buy_cost()
            self.update_used_quote()
            return order_log

        return None

    async def short(self, theo_sell: Decimal) -> Optional[dict]:
        """If we deliver order, we reflect it in balance until we read the current balance"""
        if not self.best_buyer:
            return None

        order_log = await self.order_robot.send_long_order(self.best_buyer, theo_sell)
        if order_log:
            self.pair.base.free -= self.config.base_step_qty
            self.pair.quote.free += self.approximate_sell_gain()
            self.update_used_quote()
            return order_log
        return None

    def approximate_buy_cost(self) -> Decimal:
        if self.best_seller:
            return (
                self.best_seller
                * self.config.base_step_qty
                * self.exchange.buy_with_fee
            )
        return Decimal("0")

    def approximate_sell_gain(self) -> Decimal:
        if self.best_buyer:
            return (
                self.config.base_step_qty
                * self.best_buyer
                * self.exchange.sell_with_fee
            )
        return Decimal("0")

    def update_used_quote(self) -> None:
        self.total_used_quote_amount = (
            self.start_pair.quote.total_balance - self.pair.quote.total_balance
        )

    def convert_base_to_quote(self, base_amount: Decimal) -> Decimal:
        if self.best_buyer:
            return base_amount * self.best_buyer * self.exchange.sell_with_fee
        return Decimal("0")

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            approximate_quote_for_base = self.convert_base_to_quote(
                self.pair.base.total_balance - self.start_pair.base.total_balance
            )
            return (
                self.pair.quote.total_balance
                - self.start_pair.quote.total_balance
                + approximate_quote_for_base
            )
        except Exception as e:
            logger.info(e)
            return None

    async def update_pnl(self) -> None:
        pnl = await self.calculate_pnl()
        if pnl:
            self.pnl = pnl
            self.max_pnl = max(self.max_pnl, pnl)
