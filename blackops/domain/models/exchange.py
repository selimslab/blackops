from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class ExchangeBase(ABC):
    name: str
    fee_percent: Decimal = Decimal(0)
    buy_with_fee: Decimal = Decimal(0)
    sell_with_fee: Decimal = Decimal(0)

    def __post_init__(self):
        self.buy_with_fee = Decimal(1 + self.fee_percent)
        self.sell_with_fee = Decimal(1 - self.fee_percent)

    async def get_balance(self, symbol: str) -> Optional[Decimal]:
        raise NotImplementedError

    async def short(self, price: float, qty: float, symbol: str):
        raise NotImplementedError

    async def long(self, price: float, qty: float, symbol: str):
        raise NotImplementedError

    async def get_balance_multiple(self, symbols: list) -> List[Decimal]:
        raise NotImplementedError

    @staticmethod
    def get_sales_orders(orders: dict) -> list:
        raise NotImplementedError

    @staticmethod
    def get_purchase_orders(orders: dict) -> list:
        raise NotImplementedError

    @staticmethod
    def parse_book(book: str) -> dict:
        raise NotImplementedError

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        raise NotImplementedError

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        raise NotImplementedError
