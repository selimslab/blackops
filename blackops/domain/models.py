from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator, Dict, List, Optional


@dataclass
class Asset:
    symbol: str
    balance: Decimal = Decimal(0)

    def __str__(self):
        return f"{self.symbol} {self.balance}"


@dataclass
class AssetPair:
    base: Asset
    quote: Asset

    def __post_init__(self):
        self.symbol = self.base.symbol + self.quote.symbol
        self.bt_order_symbol = self.base.symbol + "_" + self.quote.symbol

    def __str__(self):
        return f"{self.base}, {self.quote}"


@dataclass
class Exchange:
    name: str

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


@dataclass
class Client(ABC):
    ...


@dataclass
class Strategy(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    name: str

    def start(self):
        ...

    def should_long(self):
        return ...

    def should_short(self):
        return ...


@dataclass
class Trader(ABC):
    strategy: Strategy
    client: Client
