from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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

    def get_balance(self, symbol: str) -> Optional[Decimal]:
        ...


@dataclass
class Client(ABC):
    ...


@dataclass
class Strategy(ABC):
    pair: AssetPair  # base and quote currencies

    start_quote_balance: Decimal = Decimal(0)

    def start(self):
        ...

    def should_long(self):
        return ...

    def should_short(self):
        return ...


@dataclass
class TwoExchangeStrategy(Strategy):
    ...


@dataclass
class LeaderFollowerStrategy(TwoExchangeStrategy):
    """orders only on the follower"""

    ...


@dataclass
class Trader(ABC):
    strategy: Strategy
    client: Client
