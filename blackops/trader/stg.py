
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


from .bn import Binance
from .bt import Btcturk



@dataclass
class SlidingWindows(LeaderFollowerStrategy):
    """
    Move down the window as you buy, 

    it means 
    buy lower as you buy,
    go higher as you sell 

    """
    leader_exchange:Binance = Binance()
    follower_exchange:Btcturk = Btcturk()

    theo_buy = Decimal("-inf") # buy lower then theo_buy
    theo_sell = Decimal("inf") # sell higher than theo_sell

    steps = 20 # divide your money into 20 
    base_step_amount = Decimal("inf") # initially we don't know how much base coin we can get for 100 try 
    step_size_constant = Decimal(0.2) # k 
    step_size_constant_percent = Decimal(0.001) # if we don't have a manual step_size_constant, step_size_constant = mid * step_size_constant_percent


    credit = Decimal(0.75) # if we don't have a manual credit, credit could be fee_percent * Decimal(1.5) 
    # fee_percent * Decimal(1.5) 
    # Decimal(0.001)


    def __post_init__(self):
        self.set_start_balance()
        self.set_step_info()

    def set_start_balance(self):
        balance = self.follower_exchange.get_balance(self.pair.quote.symbol)
        if balance:
            self.start_quote_balance = balance 
    
    def set_step_info(self):
        self.quote_step_amount = self.start_quote_balance / self.steps  # spend 1/step TRY per step 
        self.quote_step_count = decimal_division(self.pair.quote.balance, self.quote_step_amount) # 2000 try / 100 = 20 steps 


    def should_long(self):
        return (
            self.pair.quote.balance > self.quote_step_amount
            and self.follower_exchange.best_seller < self.theo_buy
        )

    def should_short(self):
        return (
            self.pair.base.balance > self.base_step_amount and self.follower_exchange.best_buyer > self.theo_sell
        )

    def get_window_mid(self, order_book: dict) -> Optional[Decimal]:
        return self.leader_exchange.get_mid(order_book)

    def get_step_count(self)->Decimal:
         return self.quote_step_count - decimal_division(self.pair.quote.balance, self.quote_step_amount)

    def calculate_window(self, order_book: dict) -> None:
        """Update theo_buy and theo_sell"""

        if not order_book:
            return

        window_mid = self.get_window_mid(order_book)

        if not window_mid:
            return 

        # quote_step_count starts with max step, for example 20 
        # 20-20 = 0
        # 20-19 = 1
        # so step count goes up from 0,1,2,3 
        step_count = self.get_step_count()
        step_size = self.step_size_constant * step_count
        
        window_mid -= step_size # go down as you buy, we wish to buy lower as we buy 

        self.theo_buy = window_mid - self.credit
        self.theo_sell = window_mid + self.credit

