import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Optional

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.robots.config import SlidingWindowConfig
from blackops.robots.orders import OrderRobot
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

    start_base_total: Decimal = Decimal("0")
    start_quote_total: Decimal = Decimal("0")
    start_balances_set: bool = False

    total_used_quote_amount: Decimal = Decimal("0")

    pnl: Decimal = Decimal("0")
    max_pnl: Decimal = Decimal("0")

    def __post_init__(self):
        self.order_robot = OrderRobot(
            config=self.config, pair=self.pair, exchange=self.exchange
        )
        self.channnel = self.config.sha

    async def watch_follower(self):
        async for book in self.book_stream:
            if book:
                parsed_book = self.exchange.parse_book(book)
                self.update_follower_prices(parsed_book)
                self.books_seen += 1
            await asyncio.sleep(0)

    def update_follower_prices(self, book: dict):
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

    async def get_account_balance(self):
        return await self.exchange.get_account_balance()

    def set_start_balances_if_not_set(self):
        if not self.start_balances_set:
            self.start_base_total = self.pair.base.total_balance
            self.start_quote_total = self.pair.quote.total_balance
            self.start_balances_set = True

    async def update_balances(self):
        try:
            res: Optional[dict] = await self.get_account_balance()
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

            self.set_start_balances_if_not_set()

            self.update_used_quote()

        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)
            raise e

    def can_sell(self):
        return self.pair.base.free and self.pair.base.free >= self.config.base_step_qty

    def can_buy(self):
        approximate_buy_cost = self.approximate_buy_cost()
        enough_free_balance = (
            self.pair.quote.free and self.pair.quote.free >= approximate_buy_cost
        )
        will_not_exceed_the_spending_limit = (
            self.total_used_quote_amount + approximate_buy_cost
            <= self.config.max_usable_quote_amount_y
        )
        return enough_free_balance and will_not_exceed_the_spending_limit

    async def long(self, theo_buy: Decimal):
        if self.best_seller:
            ok = self.order_robot.send_long_order(self.best_seller, theo_buy)
            if ok:
                self.pair.base.free += self.config.base_step_qty
                self.pair.quote.free -= self.approximate_buy_cost()
                self.update_used_quote()
            return ok

    async def short(self, theo_sell: Decimal) -> bool:
        """If we deliver order, we reflect it in balance until we read the current balance"""
        if self.best_buyer:
            ok = self.order_robot.send_long_order(self.best_buyer, theo_sell)
            if ok:
                self.pair.base.free -= self.config.base_step_qty
                self.pair.quote.free += self.approximate_sell_gain()
                self.update_used_quote()
            return ok
        return False

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
            self.start_quote_total - self.pair.quote.total_balance
        )

    def convert_base_to_quote(self) -> Decimal:
        if self.best_buyer:
            return (
                self.pair.base.total_balance
                * self.best_buyer
                * self.exchange.sell_with_fee
            )
        return Decimal("0")

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            return (
                self.pair.quote.total_balance
                - self.start_quote_total
                + self.convert_base_to_quote()
            )
        except Exception as e:
            logger.info(e)
            return None

    async def update_pnl(self):
        pnl = await self.calculate_pnl()
        if pnl:
            self.pnl = pnl
            self.max_pnl = max(self.max_pnl, pnl)
