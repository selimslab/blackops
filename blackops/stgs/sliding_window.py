import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncGenerator, List, Optional

import blackops.util.push_events as event
from blackops.domain.models.asset import AssetPair
from blackops.domain.models.exchange import ExchangeBase
from blackops.domain.models.stg import StrategyBase
from blackops.util.logger import logger
from blackops.util.numbers import DECIMAL_2
from blackops.util.push import channel, pusher_client


@dataclass
class SlidingWindowTrader(StrategyBase):
    """
    Move down the window as you buy,

    it means
    buy lower as you buy,
    go higher as you sell

    """

    #  Params

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

    theo_buy = Decimal("-inf")  # buy lower then theo_buy
    theo_sell = Decimal("inf")  # sell higher than theo_sell

    base_step_qty = Decimal(
        "-inf"
    )  # initially we don't know how much base coin we can get for 100 try

    best_seller = Decimal("inf")
    best_buyer = Decimal("-inf")

    orders: list = field(default_factory=list)

    #  NOTES

    # if we don't have a manual step_size_constant, step_size_constant = mid *

    # if we don't have a manual credit, credit could be fee_percent *
    # Decimal(1.5)

    # fee_percent * Decimal(1.5)
    # Decimal(0.001)

    async def run(self):
        logger.info(f"Starting {self.name}")
        logger.info(self)
        await self.set_step_info()
        await self.run_streams()

    async def set_step_info(self):
        quote_balance = await self.follower_exchange.get_balance(self.pair.quote.symbol)

        if quote_balance is None:
            raise Exception("Could not get quote balance")

        self.start_quote_balance = quote_balance

        if self.max_usable_quote_amount_y < quote_balance:
            raise Exception(
                f"max_usable_quote_amount_y {self.max_usable_quote_amount_y} but quote_balance {quote_balance}"
            )

        self.remaining_usable_quote_balance = self.max_usable_quote_amount_y
        self.quote_step_qty = (
            self.remaining_usable_quote_balance / self.step_count
        )  # spend 100 TRY in 10 steps, max 1000

    async def run_streams(self):
        logger.info(f"Start streams for {self.name}")
        consumers: Any = [
            self.watch_books_and_decide(),
            self.update_best_buyers_and_sellers(),
        ]  # is this ordering important ?

        await asyncio.gather(*consumers)

    async def watch_books_and_decide(self):
        logger.info(f"Watching the leader book..")
        async for book in self.leader_book_ticker_stream:
            self.calculate_window(book)
            await self.should_transact()

    async def update_best_buyers_and_sellers(self):
        logger.info(f"Watching the follower book..")
        async for book in self.follower_book_stream:
            parsed_book = self.follower_exchange.parse_book(book)
            self.update_best_prices(parsed_book)

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
        current_step = self.get_current_step()
        step_size = self.step_constant_k * current_step

        mid -= step_size  # go down as you buy, we wish to buy lower as we buy

        self.theo_buy = mid - self.credit
        self.theo_sell = mid + self.credit

    @staticmethod
    def get_best_buyer(purchase_orders: List[dict]) -> Optional[Decimal]:
        #  best_buyer is the best price we can sell at
        if not purchase_orders:
            return None

        sorted_purchase_orders = sorted(
            purchase_orders, key=lambda d: Decimal(d["P"]), reverse=True
        )

        best_buyer = sorted_purchase_orders[0].get("P")
        if best_buyer:
            return Decimal(best_buyer)
        return None

    @staticmethod
    def get_best_seller(sales_orders: List[dict]) -> Optional[Decimal]:
        # best_seller has the lowest price we can buy at
        if not sales_orders:
            return None

        sorted_sales_orders = sorted(sales_orders, key=lambda d: Decimal(d["P"]))
        best_seller = sorted_sales_orders[0].get("P")
        if best_seller:
            return Decimal(best_seller)
        return None

    def update_best_prices(self, book: dict):
        if not book:
            return
        try:
            logger.info(book)
            sales_orders = self.follower_exchange.get_sales_orders(book)
            if sales_orders:
                best_seller = self.get_best_seller(sales_orders)
                if best_seller:
                    message = {
                        "best seller": str(self.best_seller),
                        "theo buy": str(self.theo_buy),
                    }
                    pusher_client.trigger(channel, event.update, message)
                    if best_seller < self.best_seller:
                        self.best_seller = best_seller
                        logger.info(message)

            purchase_orders = self.follower_exchange.get_purchase_orders(book)
            if purchase_orders:
                best_buyer = self.get_best_buyer(purchase_orders)
                if best_buyer:
                    message = {
                        "best buyer": str(self.best_buyer),
                        "theo sell": str(self.theo_sell),
                    }
                    pusher_client.trigger(channel, event.update, message)
                    if best_buyer > self.best_buyer:
                        self.best_buyer = best_buyer
                        logger.info(message)

        except Exception as e:
            logger.info(e)

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def should_long(self):
        return self.best_seller <= self.theo_buy

    def should_short(self):
        return self.best_buyer >= self.theo_sell

    async def long(self):
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum

        # TODO: should we consider exchange fees?
        price = self.best_seller
        if not price:
            return

        base_qty = self.quote_step_qty / price

        self.base_step_qty = max(base_qty, self.base_step_qty)

        self.remaining_usable_quote_balance -= self.quote_step_qty

        price = float(price)
        qty = float(base_qty)  #  we buy base
        symbol = self.pair.bt_order_symbol

        await self.follower_exchange.long(price, qty, symbol)

        message = {
            "long": {
                "price": str(price),
                "qty": str(qty),
                "theo_buy": str(self.theo_buy),
                "symbol": symbol,
            }
        }

        self.broadcast_order(message)

        await self.report()

    def broadcast_order(self, message):
        pusher_client.trigger(channel, event.order, message)
        self.orders.append(message)
        logger.info(message)

    async def short(self):
        price = float(self.best_buyer)
        qty = float(self.base_step_qty)  # we sell base
        symbol = self.pair.bt_order_symbol

        message = {
            "short": {
                "price": str(price),
                "qty": str(qty),
                "theo_buy": str(self.theo_sell),
                "symbol": symbol,
            }
        }

        self.broadcast_order(message)

        await self.follower_exchange.short(price, qty, symbol)

        await self.report()

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
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

    async def report(self):
        pnl = await self.calculate_pnl()
        stats = {"pnl": pnl}

        # "orders": self.orders}
        # TODO add orders to API

        logger.info(stats)
