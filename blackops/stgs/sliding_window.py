import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional

from blackops.domain.models.asset import AssetPair
from blackops.domain.models.exchange import ExchangeBase
from blackops.domain.models.stg import StrategyBase
from blackops.util.logger import logger
from blackops.util.numbers import DECIMAL_2


@dataclass
class SlidingWindow(StrategyBase):
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

    balances: Dict[str, Decimal] = field(default_factory=dict)

    base_step_qty = Decimal(
        "inf"
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
        logger.info(
            (
                self.pair,
                self.leader_exchange,
                self.follower_exchange,
                self.max_usable_quote_amount_y,
                self.step_count,
                self.credit,
                self.step_constant_k,
            )
        )
        await self.set_step_info()
        await self.run_streams()

    async def set_step_info(self):
        quote_balance = await self.follower_exchange.get_balance(self.pair.quote.symbol)

        if not quote_balance:
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

    # DECIDE

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def should_long(self):
        return (
            self.pair.quote.balance >= self.quote_step_qty
            and self.best_seller <= self.theo_buy
        )

    def should_short(self):
        return (
            self.pair.base.balance >= self.base_step_qty
            and self.best_buyer >= self.theo_sell
        )

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
        # find best_buyer
        if not purchase_orders:
            return None

        sorted_purchase_orders = sorted(
            purchase_orders, key=lambda d: float(d["P"]), reverse=True
        )

        best_buyer = sorted_purchase_orders[0].get("P", "")
        return Decimal(best_buyer)

    @staticmethod
    def get_best_seller(sales_orders: List[dict]) -> Optional[Decimal]:
        # find best_seller
        if not sales_orders:
            return None

        sorted_sales_orders = sorted(sales_orders, key=lambda d: float(d["P"]))
        best_seller = sorted_sales_orders[0].get("P", "")
        return Decimal(best_seller)

    def update_best_prices(self, book: dict):
        if not book:
            return
        try:
            sales_orders = self.follower_exchange.get_sales_orders(book)
            if sales_orders:
                best_seller = self.get_best_seller(sales_orders)
                if best_seller and best_seller < self.best_seller:
                    self.best_seller = best_seller
                    logger.info(f"Best seller updated to {self.best_seller}")

            purchase_orders = self.follower_exchange.get_purchase_orders(book)
            if purchase_orders:
                best_buyer = self.get_best_buyer(purchase_orders)
                if best_buyer and best_buyer > self.best_buyer:
                    self.best_buyer = best_buyer
                    logger.info(f"Best buyer updated to {self.best_buyer}")

        except Exception as e:
            logger.info(e)

    async def long(self):
        cost = self.best_seller * self.follower_exchange.buy_with_fee
        base_qty = self.quote_step_qty / cost

        self.base_step_qty = min(base_qty, self.base_step_qty)

        self.remaining_usable_quote_balance -= cost

        price = float(self.best_seller)
        qty = float(base_qty)  #  we buy base
        symbol = self.pair.bt_order_symbol

        self.orders.append(("buy", price, qty, symbol))

        await self.follower_exchange.long(price, qty, symbol)

        await self.report()

    async def short(self):

        price = float(self.best_buyer)
        qty = float(self.base_step_qty)  # we sell base
        symbol = self.pair.bt_order_symbol

        self.orders.append(("sell", price, qty, symbol))

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
                base_balance * self.best_buyer * self.follower_exchange.sell_with_fee
            )
            return quote_balance + approximate_sales_gain - self.start_quote_balance
        except Exception as e:
            logger.info(e)
            return None

    async def report(self):
        pnl = await self.calculate_pnl()
        stats = {"pnl": pnl, "orders": self.orders}

        logger.info(stats)