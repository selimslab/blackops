from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator, Dict, List, Optional


@dataclass
class Exchange:
    name: str
    fee_percent: Decimal
    buy_with_fee: Decimal
    sell_with_fee: Decimal

    @abstractmethod
    def get_balance(self, symbol: str) -> Optional[Decimal]:
        ...

    @abstractmethod
    async def short(self, price: float, qty: float, symbol: str):
        ...

    @abstractmethod
    async def long(self, price: float, qty: float, symbol: str):
        ...

    @abstractmethod
    def get_balance_multiple(self, symbols: list) -> List[Decimal]:
        ...

    @abstractmethod
    @staticmethod
    def get_sales_orders(orders: dict) -> list:
        ...

    @abstractmethod
    @staticmethod
    def get_purchase_orders(orders: dict) -> list:
        ...

    @abstractmethod
    async def orderbook_stream(self, symbol: str) -> AsyncIterator[dict]:
        ...

    @abstractmethod
    @staticmethod
    async def book_ticker_stream(symbol: str) -> AsyncIterator[dict]:
        ...
