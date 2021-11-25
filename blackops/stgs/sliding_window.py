import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, List, Optional

import blackops.pubsub.pub as pub
from blackops.domain.models.asset import AssetPair
from blackops.domain.models.exchange import ExchangeBase
from blackops.domain.models.stg import StrategyBase
from blackops.environment import is_prod
from blackops.taskq.redis import async_redis_client
from blackops.util.logger import logger
from blackops.util.numbers import DECIMAL_2


@dataclass
class SlidingWindowTrader(StrategyBase):
    """
    Move down the window as you buy,

    it means
    buy lower as you buy,
    go higher as you sell

    """

    #  Params

    sha: str

    pair: AssetPair

    max_usable_quote_amount_y: Decimal

    step_count: Decimal  # divide your money into 20

    credit: Decimal

    step_constant_k: Decimal

    # Exchanges

    leader_exchange: ExchangeBase
    follower_exchange: ExchangeBase

    leader_book_ticker_stream: AsyncGenerator
    follower_book_stream: AsyncGenerator

    # Internals

    name: str = "sliding_window"

    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None

    task_start_time: datetime = datetime.now()
    theo_last_updated: datetime = datetime.now()
    bid_ask_last_updated: datetime = datetime.now()
    time_diff: float = 0

    base_step_qty: Decimal = Decimal("1")
    quote_step_qty: Decimal = Decimal("1")

    orders: list = field(default_factory=list)

    pnl: Decimal = Decimal("0")
    pnl_last_updated: datetime = datetime.now()

    binance_book_ticker_stream_seen: int = 0
    btc_books_seen: int = 0

    start_quote_balance: Decimal = Decimal("0")
    start_base_balance: Decimal = Decimal("0")

    current_step: Decimal = Decimal("0")

    remaining_usable_quote_balance: Decimal = Decimal("0")

    #  NOTES

    # if we don't have a manual step_size_constant, step_size_constant = mid *

    # if we don't have a manual credit, credit could be fee_percent *
    # Decimal(1.5)

    # fee_percent * Decimal(1.5)
    # Decimal(0.001)

    async def init(self):
        self.channnel = self.sha

        await self.set_step_info()

        self.params_message = self.create_params_message()
        pub.publish_params(self.channnel, self.params_message)
        logger.info(self.params_message)

    async def run(self):
        await self.init()
        await self.run_streams()

    def get_orders(self):
        return self.orders

    async def set_step_info(self):
        # TODO : 90 rate limit
        try:
            (
                self.pair.base.balance,
                self.pair.quote.balance,
            ) = await self.follower_exchange.get_balance_multiple(
                [self.pair.base.symbol, self.pair.quote.symbol]
            )
        except Exception as e:
            msg = "could not read balances"
            pub.publish_error(self.channnel, msg)
            raise Exception(msg)

        self.start_base_balance = self.pair.base.balance
        self.start_quote_balance = self.pair.quote.balance

        if self.max_usable_quote_amount_y < self.pair.quote.balance:
            msg = f"max_usable_quote_amount_y {self.max_usable_quote_amount_y} but quote_balance {self.pair.quote.balance}"

            pub.publish_error(self.channnel, msg)

            raise Exception(msg)

        self.remaining_usable_quote_balance = self.max_usable_quote_amount_y
        self.quote_step_qty = (
            self.remaining_usable_quote_balance / self.step_count
        )  # spend 100 TRY in 10 steps, max 1000

    async def run_streams(self):
        logger.info(f"Start streams for {self.name}")

        consumers: Any = [
            self.watch_books_and_decide(),
            self.update_best_buyers_and_sellers(),
            self.broadcast_stats_periodical(),
        ]  # is this ordering important ?

        await asyncio.gather(*consumers)

    async def watch_books_and_decide(self):
        pub.publish_message(
            self.channnel, f"Watching books of {self.leader_exchange.name}"
        )

        async for book in self.leader_book_ticker_stream:
            if book:
                self.binance_book_ticker_stream_seen += 1
                self.calculate_window(book)
                await self.should_transact()
            await asyncio.sleep(0)

    async def update_best_buyers_and_sellers(self):
        logger.info(f"Watching the follower book..")
        pub.publish_message(
            self.channnel, f"Watching books of {self.follower_exchange.name}"
        )
        async for book in self.follower_book_stream:
            if book:
                self.btc_books_seen += 1
                parsed_book = self.follower_exchange.parse_book(book)
                self.update_best_prices(parsed_book)
            await asyncio.sleep(0)

    def get_current_step(self) -> Decimal:
        # for example 20
        # 20-20 = 0
        # 20-19 = 1

        # max_qu

        remaining_steps = self.remaining_usable_quote_balance / self.quote_step_qty
        return self.step_count - remaining_steps

    def get_mid(self, book: dict) -> Optional[Decimal]:
        best_bid = self.leader_exchange.get_best_bid(book)
        best_ask = self.leader_exchange.get_best_ask(book)

        if not best_bid or not best_ask:
            return None

        mid = (best_bid + best_ask) / DECIMAL_2

        if mid:
            return mid

        return None

    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""

        if not book:
            return

        mid = self.get_mid(book)

        if not mid:
            return

        #  0,1,2,3, n-1
        self.current_step = self.get_current_step()
        step_size = self.step_constant_k * self.current_step

        mid -= step_size  # go down as you buy, we wish to buy lower as we buy

        self.theo_buy = mid - self.credit
        self.theo_sell = mid + self.credit

        self.theo_last_updated = datetime.now()
        self.time_diff = (
            self.theo_last_updated - self.bid_ask_last_updated
        ).total_seconds()

    def update_best_prices(self, book: dict):
        if not book:
            return
        try:
            sales_orders = self.follower_exchange.get_sales_orders(book)
            if sales_orders:
                prices = [order.get("P") for order in sales_orders]
                prices = [Decimal(price) for price in prices if price]
                best_ask = min(prices)
                if best_ask:
                    self.best_seller = best_ask

            purchase_orders = self.follower_exchange.get_purchase_orders(book)
            if purchase_orders:
                prices = [order.get("P") for order in purchase_orders]
                prices = [Decimal(price) for price in prices if price]
                best_bid = max(prices)
                if best_bid:
                    self.best_buyer = best_bid

            self.bid_ask_last_updated = datetime.now()
            self.time_diff = (
                self.theo_last_updated - self.bid_ask_last_updated
            ).total_seconds()

        except Exception as e:
            logger.info(e)

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def should_long(self):
        #  act only when you are ahead
        return (
            self.best_seller
            and self.theo_buy
            and self.time_diff > -0.1
            and self.best_seller <= self.theo_buy
        )

    def should_short(self):
        #  act only when you are ahead
        return (
            self.best_buyer
            and self.theo_sell
            and self.time_diff > -0.1
            and self.best_buyer >= self.theo_sell
        )

    async def long(self):
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum

        # TODO: should we consider exchange fees?

        if not self.best_seller or not self.quote_step_qty:
            return

        base_qty = self.quote_step_qty / self.best_seller

        if base_qty:
            self.base_step_qty = base_qty

        price = float(self.best_seller)
        qty = float(base_qty)  #  we buy base
        symbol = self.pair.bt_order_symbol

        try:
            await self.follower_exchange.long(price, qty, symbol)
            quote_balance = await self.follower_exchange.get_balance(
                self.pair.quote.symbol
            )
            if quote_balance:
                self.remaining_usable_quote_balance = quote_balance

            order = {
                "type": "long",
                "price": str(price),
                "qty": str(qty),
                "theo_buy": str(self.theo_buy),
            }
            self.log_order(order)
            await self.update_pnl()
        except Exception as e:
            logger.info(e)

    def log_order(self, order: dict):
        if is_prod:
            pub.publish_order(self.channnel, order)
        self.orders.append(order)
        logger.info(order)

    async def short(self):
        if not self.best_buyer or not self.base_step_qty:
            return

        price = float(self.best_buyer)
        qty = float(self.base_step_qty)  # we sell base
        symbol = self.pair.bt_order_symbol

        try:
            await self.follower_exchange.short(price, qty, symbol)
            quote_balance = await self.follower_exchange.get_balance(
                self.pair.quote.symbol
            )
            if quote_balance:
                self.remaining_usable_quote_balance = quote_balance

            order = {
                "type": "short",
                "price": str(price),
                "qty": str(qty),
                "theo_sell": str(self.theo_sell),
            }
            self.log_order(order)
            await self.update_pnl()

        except Exception as e:
            logger.info(e)

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            if not self.start_quote_balance:
                return None

            (
                base_balance,
                quote_balance,
            ) = await self.follower_exchange.get_balance_multiple(
                [self.pair.base.symbol, self.pair.quote.symbol]
            )
            approximate_sales_gain: Decimal = (
                base_balance * self.best_buyer * self.follower_exchange.api_client.sell_with_fee  # type: ignore
            )

            return quote_balance + approximate_sales_gain - self.start_quote_balance
        except Exception as e:
            logger.info(e)
            return None

    async def update_pnl(self):
        pnl = await self.calculate_pnl()
        if pnl:
            self.pnl = pnl

    def create_params_message(self):
        return {
            "name": self.name,
            "pair": self.pair.symbol,
            "max_usable_quote_amount_y": str(self.max_usable_quote_amount_y),
            "step_constant_k": str(self.step_constant_k),
            "credit": str(self.credit),
            "step_count": str(self.step_count),
            "task_start_time": str(self.task_start_time),
            "start_base_balance": str(self.start_base_balance),
            "start_quote_balance": str(self.start_quote_balance),
        }

    def create_stats_message(self):
        stats = {
            "time": str(datetime.now().time()),
            "runtime": str((datetime.now() - self.task_start_time).total_seconds()),
            "theo_buy": str(self.theo_buy),
            "theo_sell": str(self.theo_sell),
            "theo_last_updated": str(self.theo_last_updated.time()),
            "pnl": str(self.pnl),
            "base_balance": str(self.pair.base.balance),
            "quote_balance": str(self.pair.quote.balance),
            "remaining_usable_quote_balance": str(self.remaining_usable_quote_balance),
            "current_step": str(self.current_step),
            "orders": len(self.orders),
            "best_ask": str(self.best_seller),
            "best_bid": str(self.best_buyer),
            "bid_ask_last_updated": str(self.bid_ask_last_updated.time()),
            "binance_seen": self.binance_book_ticker_stream_seen,
            "btc_seen": self.btc_books_seen,
            "time_diff": self.time_diff,
        }
        if is_prod:
            stats["params"] = self.params_message

        return stats

    def broadcast_stats(self):
        message = self.create_stats_message()
        if is_prod:
            pub.publish_stats(self.channnel, message)
        else:
            keys = {
                "runtime",
                "pnl",
                "orders",
                "binance_seen",
                "btc_seen",
                "time_diff",
            }
            logger.info({k: v for k, v in message.items() if k in keys})

    async def broadcast_stats_periodical(self):
        while True:
            self.broadcast_stats()
            await asyncio.sleep(0.5)
