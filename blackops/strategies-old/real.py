import asyncio
import collections
import json
import operator
import pprint
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, List, Optional

from aiostream import async_, stream

from blackops.clients.binance.stream import ws_generator_binance
from blackops.clients.btcturk.main import Client, btcturk_client
from blackops.clients.btcturk.stream import ws_generator_bt
from blackops.domain.models import Asset, AssetPair, Exchange, Strategy
from blackops.logger import logger
from blackops.util import decimal_division, decimal_mid


@dataclass
class WindowBreaker(Strategy):
    """
    Move down the window as you buy, 

    it means 
    buy lower as you buy,
    go higher as you sell 

    
    """

    pair: AssetPair # base and quote currencies 

    client = btcturk_client 

    bridge: Optional[Asset] = None 

    theo_buy = Decimal("-inf") # buy lower then theo_buy
    theo_sell = Decimal("inf") # sell higher than theo_sell

    # if connection is lost, we reset these two, should we? probably yes 
    best_seller = Decimal("inf")
    best_buyer = Decimal("-inf")
    
    steps = 20 # divide your money into 20 

    base_step_amount = Decimal("inf") # initially we don't know how much base coin we can get for 100 try 

    step_size_constant = Decimal(0.2) # k 

    step_size_constant_percent = Decimal(0.001) # if we don't have a manual step_size_constant, step_size_constant = mid * step_size_constant_percent

    fee_percent = Decimal(0.0018) # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we sell 

    buy_with_fee = Decimal(1 + fee_percent)
    sell_with_fee = Decimal(1 - fee_percent)

    credit = Decimal(0.75) # if we don't have a manual credit, credit could be fee_percent * Decimal(1.5) 
    # fee_percent * Decimal(1.5) 
    # Decimal(0.001)

    def __post_init__(self):
        if self.bridge:
            self.bridge_base_pair = AssetPair(self.pair.base, self.bridge)
            self.bridge_quote_pair = AssetPair(self.bridge, self.pair.quote)

        self.start_quote_balance = self.get_balance([self.pair.quote.symbol])[0]
        self.quote_step_amount = self.start_quote_balance / self.steps  # spend 1/step TRY per step 

        self.bridge_quote = Decimal(1)

        self.quote_step_count = decimal_division(self.pair.quote.balance, self.quote_step_amount) # 2000 try / 100 = 20 steps 

    async def run(self):
        aws: Any = self.get_consumers()

        aws.append(self.periodic_report(10))  # optional 

        await asyncio.gather(*aws)
    

    # CLIENT 
    @staticmethod
    def get_balance(symbols:list):
        try:
            res_list = btcturk_client.get_account_balance(assets=symbols)
            str_balances = [r.get("balance") for r in res_list)
            decimal_balances = [Decimal(b) for b in str_balances]
            return decimal_balances
        except Exception:
            raise Exception("couldnt read balance")


    # CONSUMERS
    def get_consumers(self):
        if self.bridge:
            aws = [
                self.consume_binance_orderbook_stream(self.bridge_base_pair.symbol),
                self.consume_binance_bridge_quote_stream(self.bridge_quote_pair.symbol),
                self.consume_bt_orderbook_stream(self.pair.symbol),
            ]

        else:
            aws = [
                self.consume_binance_orderbook_stream(self.pair.symbol),
                self.consume_bt_orderbook_stream(self.pair.symbol),
            ]

        return aws

    async def consume_bt_orderbook_stream(self, symbol: str):
        async for bt_order_book in ws_generator_bt(symbol):
            if bt_order_book:
                await self.process_bt_order_book(bt_order_book)

    async def consume_binance_orderbook_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                await self.process_binance_order_book(binance_order_book)
                await self.should_transact()

    async def consume_binance_bridge_quote_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                self.bridge_quote = self.get_binance_mid(binance_order_book)

    # DECIDE 
    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def should_long(self):
        return (
            self.pair.quote.balance > self.quote_step_amount
            and self.best_seller < self.theo_buy
        )

    def should_short(self):
        return (
            self.pair.base.balance > self.base_step_amount and self.best_buyer > self.theo_sell
        )

    # EXECUTE  
    async def long(self):
        cost = self.best_seller * self.buy_with_fee
        qty = decimal_division(self.quote_step_amount, cost)
        self.base_step_amount = min(self.base_step_amount, qty)


        self.client.submit_limit_order(
            quantity=float(qty),
            price=float(self.best_seller),
            order_type='buy',
            pair_symbol=self.pair.bt_order_symbol
        )

    async def short(self):
        self.client.submit_limit_order(
            quantity=float(self.base_step_amount),
            price=float(self.best_buyer),
            order_type='sell',
            pair_symbol=self.pair.bt_order_symbol
        )


    # STREAM PROCESSING 
    @staticmethod
    def get_best_buyer(purchase_orders):
        # find best_buyer
        if purchase_orders:
            sorted_purchase_orders = sorted(
                purchase_orders, key=operator.itemgetter("P"), reverse=True
            )
            if not sorted_purchase_orders:
                return
            best_buyer = sorted_purchase_orders[0].get("P")
            if best_buyer:
                return Decimal(best_buyer)

    @staticmethod
    def get_best_seller(sales_orders):
        # find best_seller
        if sales_orders:
            sorted_sales_orders = sorted(sales_orders, key=operator.itemgetter("P"))
            if not sorted_sales_orders:
                return
            best_seller = sorted_sales_orders[0].get("P")
            if best_seller:
                return Decimal(best_seller)

    @staticmethod
    def get_bt_order_list(orderbook:str):
        try:
            order_book = json.loads(orderbook)

            order_book: dict = order_book[1]

            sales_orders = order_book.get("AO", [])
            purchase_orders = order_book.get("BO", [])

            return sales_orders, purchase_orders
        except Exception as e:
            print(e)
            return (None, None)

    async def process_bt_order_book(self, order_book: str):
        """Update best_buyer and best_seller"""
        if not order_book:
            return

        sales_orders, purchase_orders = self.get_bt_order_list(order_book)

        best_buyer = self.get_best_buyer(purchase_orders)
        best_seller = self.get_best_seller(sales_orders)

        # update best_seller and best_buyer
        if best_seller and best_buyer:
            self.best_seller = min(self.best_seller, best_seller)
            self.best_buyer = max(self.best_buyer, best_buyer)


    def get_binance_mid(self, order_book: dict):
        """ get mid price from binance orderbook  """
        order_book = order_book.get("data", {})

        best_ask_price = order_book.get("a", 0)
        best_bid_price = order_book.get("b", 0)

        mid: Decimal = decimal_mid(best_ask_price, best_bid_price)

        return mid

    async def process_binance_order_book(self, order_book: dict) -> None:
        """Update theo_buy and theo_sell"""

        if not order_book:
            return

        # bridge_quote for bridging, xusdt -> usdtry -> xtry
        mid = self.get_binance_mid(order_book) * self.bridge_quote

        # quote_step_count starts with max step, for example 20 
        # 20-20 = 0
        # 20-19 = 1
        # so step count goes up from 0,1,2,3 
        step_count = self.quote_step_count - decimal_division(self.pair.quote.balance, self.quote_step_amount)
        step_size = self.step_size_constant * step_count
        mid -= step_size # go down as you buy, we wish to buy lower as we buy 

        self.theo_buy = mid - self.credit
        self.theo_sell = mid + self.credit

    # REPORTING 
    def calculate_pnl(self):
        try:
            base_balance, quote_balance  = self.get_balance([self.pair.base.symbol, self.pair.quote.symbol])
            approximate_sales_gain:Decimal = base_balance * self.best_buyer * self.sell_with_fee
            return quote_balance + approximate_sales_gain - self.start_quote_balance
        except Exception:
            pass


    def log_report(self):

        pnl = self.calculate_pnl()

        logger.info(
            f"""
        pnl: {pnl}

        target buy: {self.theo_buy}
        best seller: {self.best_seller}

        target sell: {self.theo_sell}
        best buyer: {self.best_buyer}
        """
        )


    async def periodic_report(self, period: float):
        while True:
            self.log_report()
            await asyncio.sleep(period)


from enum import Enum


class OrderType(Enum):
    buy = 'buy'
    sell = 'sell'


@dataclass
class Order:
    ...


@dataclass
class LimitOrder(Order):
    type: OrderType
    qty: Decimal



@dataclass
class Report:
    ...


@dataclass
class PeriodicReport(Report):
    pnl: Decimal

    target_buy: Decimal
    best_seller: Decimal 
    
    target_sell:Decimal
    best_buyer: Decimal 

