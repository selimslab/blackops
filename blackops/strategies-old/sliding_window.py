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
class TradeStats:
    exchanges: List[Exchange] = field(default_factory=list)
    order_books_seen: dict = field(default_factory=lambda: collections.defaultdict(int))
    seconds: float = 0
    pnl = Decimal(0)

    def __str__(self):
        return f"pnl {self.pnl}, in {self.seconds}"
        # , seen books {dict(self.order_books_seen)}




@dataclass
class SlidingWindow(Strategy):

    pair: AssetPair # base and quote currencies 

    client: Optional[Client] = None  

    bridge: Optional[Asset] = None 

    theo_buy = Decimal("-inf") # buy lower then theo_buy
    theo_sell = Decimal("inf") # sell higher than theo_sell

    # if connection is lost, we reset these two, should we? probably yes 
    best_seller = Decimal("inf")
    best_buyer = Decimal("-inf")
    
    base_step_amount = Decimal("inf") # initially we don't know how much base coin we can get for 100 try 
    quote_step_amount = Decimal(500) # 20 steps  

    step_size_constant = Decimal(0.2) # k 

    step_size_constant_percent = Decimal(0.001) # if we don't have a manual step_size_constant, step_size_constant = mid * step_size_constant_percent

    fee_percent = Decimal(0.0018) # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we sell 

    credit = Decimal(0.75) # if we don't have a manual credit, credit could be fee_percent * Decimal(1.5) 
    # fee_percent * Decimal(1.5) 
    # Decimal(0.001)

    stats = TradeStats()

    def __post_init__(self):
        if self.bridge:
            self.bridge_base_pair = AssetPair(self.pair.base, self.bridge)
            self.bridge_quote_pair = AssetPair(self.bridge, self.pair.quote)

        self.start_quote_balance = self.pair.quote.balance

        self.bridge_quote = Decimal(1)

        self.quote_step_count = decimal_division(self.pair.quote.balance, self.quote_step_amount)

    async def run(self):
        self.stream_start_time = time.time()
        aws: Any = self.get_sources()
        # aws.append(self.periodic_report(5))
        await asyncio.gather(*aws)

    async def generic_publish(self, stream, consumer: Callable):
        async for item in stream:
            print(item)
            await consumer(item)

    def get_sources(self):
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
                self.stats.order_books_seen["bt"] += 1

    async def consume_binance_orderbook_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                await self.process_binance_order_book(binance_order_book)
                await self.should_transact()
                self.stats.order_books_seen["bn"] += 1

    async def consume_binance_bridge_quote_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                self.bridge_quote = self.get_binance_mid(binance_order_book)

    # DECIDE 
    async def should_transact(self):
        if self.should_long():

            await self.dummy_long()

        if self.should_short():
   
            await self.dummy_short()

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
    async def dummy_long(self):

        qty = decimal_division(self.quote_step_amount, self.best_seller * Decimal(1 + self.fee_percent))
        self.base_step_amount = min(self.base_step_amount, qty)
        self.pair.quote.balance -= self.quote_step_amount
        self.pair.base.balance += qty

        order = {
            'qty':qty,
            'price': self.best_seller,
            'type':'buy',
            'symbol': self.pair.bt_order_symbol
        }
        logger.critical(order)
        logger.info(
            f"bought {round(qty,2)} {self.pair.base.symbol} at {self.best_seller} for {round(self.best_seller*qty,2)} {self.pair.quote.symbol}  \n"
        )
        self.print_report()

    async def dummy_short(self):
        gross = self.base_step_amount * self.best_buyer  *  Decimal(1 - self.fee_percent)
        self.pair.base.balance -= self.base_step_amount
        self.pair.quote.balance += gross

        order = {
            'qty':self.base_step_amount,
            'price': self.best_buyer,
            'type':'sell',
            'symbol': self.pair.bt_order_symbol
        }

        logger.critical(order)
        logger.info(
            f"sold {self.base_step_amount} {self.pair.base.symbol} for {round(gross,2)} {self.pair.quote.symbol}"
        )
        self.print_report()


    # STREAM PROCESSING 
    async def process_bt_order_book(self, order_book: str):
        """Update best_buyer and best_seller"""
        if not order_book:
            return
        try:
            order_book = json.loads(order_book)

            order_book: dict = order_book[1]

        except Exception as e:
            logger.info(e)
            return

        if not order_book:
            return

        sales_orders = order_book.get("AO", [])
        purchase_orders = order_book.get("BO", [])

        # find best_seller
        sorted_sales_orders = sorted(sales_orders, key=operator.itemgetter("P"))
        if not sorted_sales_orders:
            return
        best_seller = sorted_sales_orders[0].get("P")

        # find best_buyer
        sorted_purchase_orders = sorted(
            purchase_orders, key=operator.itemgetter("P"), reverse=True
        )
        if not sorted_purchase_orders:
            return
        best_buyer = sorted_purchase_orders[0].get("P")
        
        # update best_seller and best_buyer
        if best_seller and best_buyer:
            best_seller = Decimal(best_seller) 
            best_buyer = Decimal(best_buyer) 

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

        # xusdt -> usdtry -> xtry
        mid = self.get_binance_mid(order_book) * self.bridge_quote

        # step_size = mid * self.step_size_percent

        # 20 -20 = 0, 20-19 = 1, 
        step_count = self.quote_step_count - decimal_division(self.pair.quote.balance, self.quote_step_amount)
        step_size = self.step_size_constant * step_count
        mid -= step_size # go down as you buy, we wish to buy lower as we buy 

        self.theo_buy = mid - self.credit
        self.theo_sell = mid + self.credit

    # REPORTING 
    def calculate_pnl(self):
        approximate_sales_gain = 0
        try:
            approximate_sales_gain = self.pair.base.balance * self.best_buyer
        except Exception:
            pass
        return self.pair.quote.balance  + approximate_sales_gain - self.start_quote_balance


    def print_report(self):
        # print(f"seen {bn} bn, {bt} bt books in {} secs")

        self.stats.seconds = round(time.time() - self.stream_start_time, 2)
        self.stats.pnl = self.calculate_pnl()

        if self.best_seller and self.theo_buy:
            ...
        logger.info(
            f"""
        {self.pair}

        {self.stats}

        target buy: {self.theo_buy}
        best seller: {self.best_seller}
        """
        )

        """

        target sell: {self.theo_sell}
        best buyer: {self.best_buyer}
        """

    async def periodic_report(self, period: float):
        while True:
            self.print_report()
            await asyncio.sleep(period)
