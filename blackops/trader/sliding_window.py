
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from blackops.domain.models import LeaderFollowerStrategy
from blackops.exchanges.binance.main import Binance
from blackops.exchanges.btcturk.main import Btcturk
from blackops.util.decimal import decimal_division, decimal_mid
from blackops.util.logger import logger


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
    step_size_constant = Decimal(0.2) # k 
    step_size_constant_percent = Decimal(0.001) # if we don't have a manual step_size_constant, step_size_constant = mid * step_size_constant_percent

    credit = Decimal(0.75) # if we don't have a manual credit, credit could be fee_percent * Decimal(1.5) 
    
    
    # fee_percent * Decimal(1.5) 
    # Decimal(0.001)

    base_step_qty = Decimal("inf") # initially we don't know how much base coin we can get for 100 try 


    def __post_init__(self):
        self.set_start_balance()
        self.set_step_info()

    def set_start_balance(self):
        balance = self.follower_exchange.get_balance(self.pair.quote.symbol)
        if balance:
            self.start_quote_balance = balance 
    
    def set_step_info(self):
        self.quote_step_qty = self.start_quote_balance / self.steps  # spend 1/step TRY per step 
        self.quote_step_count = decimal_division(self.pair.quote.balance, self.quote_step_qty) # 2000 try / 100 = 20 steps 

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def should_long(self):
        return (
            self.pair.quote.balance > self.quote_step_qty
            and self.follower_exchange.best_seller < self.theo_buy
        )

    def should_short(self):
        return (
            self.pair.base.balance > self.base_step_qty and self.follower_exchange.best_buyer > self.theo_sell
        )

    async def long(self):
        cost = self.follower_exchange.best_seller * self.follower_exchange.buy_with_fee
        qty = decimal_division(self.quote_step_qty, cost)

        if qty < self.base_step_qty:
            self.base_step_qty = qty 

        await self.follower_exchange.long(float(self.follower_exchange.best_seller), float(qty), self.pair.bt_order_symbol)

    async def short(self):
        await self.follower_exchange.short(float(self.follower_exchange.best_buyer), float(self.quote_step_qty), self.pair.bt_order_symbol)




    def get_window_mid(self, order_book: dict) -> Optional[Decimal]:
        return self.leader_exchange.get_mid(order_book)

    def get_step_count(self)->Decimal:
         return self.quote_step_count - decimal_division(self.pair.quote.balance, self.quote_step_qty)

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




    async def run_streams(self):
        consumers:Any = [
                self.watch_books_and_decide(self.pair.symbol),
                self.update_best_buyers_and_sellers(self.pair.symbol)
            ]
        # aws.append(self.periodic_report(10))  # optional 
        await asyncio.gather(*consumers)
    

    async def watch_books_and_decide(self, symbol: str):
        async for book in self.leader_exchange.book_ticker_stream(symbol):
            self.calculate_window(book)
            await self.should_transact()

    async def update_best_buyers_and_sellers(self, symbol:str):
        async for book in self.follower_exchange.orderbook_stream(symbol):
            self.follower_exchange.update_best_prices(book)


