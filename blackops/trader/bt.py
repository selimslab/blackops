import asyncio
import collections
import json
import operator
import pprint
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable, List, Optional

from aiostream import async_, stream

from blackops.clients.binance.stream import ws_generator_binance
from blackops.clients.btcturk.main import Client, btcturk_client
from blackops.clients.btcturk.stream import ws_generator_bt
from blackops.domain.models import Asset, AssetPair, Exchange, LeaderFollowerStrategy
from blackops.logger import logger
from blackops.util import decimal_division, decimal_mid




@dataclass
class Btcturk(Exchange):

    client = btcturk_client

    name:str = "btcturk"

    fee_percent = Decimal(0.0018) # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we sell 
    buy_with_fee = Decimal(1 + fee_percent)
    sell_with_fee = Decimal(1 - fee_percent)


    # if connection is lost, we reset these two, should we? probably yes 
    best_seller = Decimal("inf")
    best_buyer = Decimal("-inf")

    def __post_init__(self):
        ...
    
    def get_balance_multiple(self, symbols:list)->list:
        try:
            res_list = self.client.get_account_balance(assets=symbols)
            str_balances = [r.get("balance") for r in res_list)
            decimal_balances = [Decimal(b) for b in str_balances]
            return decimal_balances
        except Exception as e:
            logger.info(f"could not read balances: {e}")
            return []


    def get_balance(self, symbol:str)->Optional[Decimal]:
        balance_list = self.get_balance_multiple([symbol])
        if balance_list:
            return  balance_list[0]
  

    async def long(self, price, qty):
        cost = self.best_seller * self.buy_with_fee
        qty = decimal_division(self.quote_step_amount, cost)
        self.base_step_amount = min(self.base_step_amount, qty)


        self.client.submit_limit_order(
            quantity=float(qty),
            price=float(self.best_seller),
            order_type='buy',
            pair_symbol=self.pair.bt_order_symbol
        )

    async def short(self, price,qty):
        self.client.submit_limit_order(
            quantity=float(self.base_step_amount),
            price=float(self.best_buyer),
            order_type='sell',
            pair_symbol=self.pair.bt_order_symbol
        )



    @staticmethod
    def get_best_buyer(purchase_orders:List[dict])->Optional[Decimal]:
        # find best_buyer
        if not purchase_orders:
            return 
        
        sorted_purchase_orders = sorted(
            purchase_orders, key=operator.itemgetter("P"), reverse=True
        )
        if not sorted_purchase_orders:
            return

        best_buyer = sorted_purchase_orders[0].get("P")
        if not best_buyer:
            return 

        return Decimal(best_buyer)

    @staticmethod
    def get_best_seller(sales_orders:List[dict])->Optional[Decimal]:
        # find best_seller
        if not sales_orders:
            return 

        sorted_sales_orders = sorted(sales_orders, key=operator.itemgetter("P"))
        if not sorted_sales_orders:
            return

        best_seller = sorted_sales_orders[0].get("P")
        if not best_seller:
            return 

        return Decimal(best_seller)



    @staticmethod
    def get_sales_orders(orders:dict)->list:
        try:
            sales_orders = orders.get("AO", [])
            return sales_orders
        except Exception as e:
            logger.info(e)
            return []

    @staticmethod
    def get_purchase_orders(orders:dict)->list:
        try:
            purchase_orders = orders.get("BO", [])
            return purchase_orders
        except Exception as e:
            logger.info(e)
            return []

    @staticmethod
    def parse_orderbook( orderbook: str)->dict:
        try:
            orders = json.loads(orderbook)
            orders: dict = orders[1]
            return orders
        except Exception as e:
            logger.info(e)
            return {}


    def update_best_prices(self, orders:dict):
        if not orders:
            return 

        sales_orders = self.get_sales_orders(orders)
        if sales_orders:
            best_seller = self.get_best_seller(sales_orders)
            if best_seller and best_seller < self.best_seller:
                self.best_seller = best_seller

        purchase_orders = self.get_purchase_orders(orders)
        if purchase_orders:
            best_buyer = self.get_best_buyer(purchase_orders)
            if best_buyer and best_buyer > self.best_buyer:
                self.best_buyer = best_buyer


    def process_order_book(self, orderbook: str):
        orders = self.parse_orderbook(orderbook)
        self.update_best_prices(orders)
    


    async def consume_orderbook_stream(self, book_generator):
        async for book in book_generator:
            if book:
                parsed = self.parse_orderbook(book)
                if parsed:
                    self.update_best_prices(parsed)



    def calculate_pnl(self, pair:AssetPair, start_quote_balance:Decimal)->Optional[Decimal]:
        try:
            base_balance, quote_balance  = self.get_balance_multiple([pair.base.symbol, pair.quote.symbol])
            approximate_sales_gain:Decimal = base_balance * self.best_buyer * self.sell_with_fee
            return quote_balance + approximate_sales_gain - start_quote_balance
        except Exception as e:
            logger.info(e)
            
    

