from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.periodic import StopwatchAPI


@dataclass
class Prices:
    sell: Decimal
    buy: Decimal


@dataclass
class TargetPrices:
    maker: Optional[Prices] = None
    taker: Optional[Prices] = None


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class FeeBPS:
    taker: Decimal = Decimal("8")
    maker: Decimal = Decimal("4")


@dataclass
class CreditConstantsBPS:
    sell: Decimal = Decimal(0)
    hold: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


@dataclass
class CreditConstants:
    taker: CreditConstantsBPS = field(default_factory=CreditConstantsBPS)
    maker: CreditConstantsBPS = field(default_factory=CreditConstantsBPS)


@dataclass
class Credits:
    buy: Decimal = Decimal(0)
    sell: Decimal = Decimal(0)


@dataclass
class Signals:
    buy: Decimal = Decimal(0)
    sell: Decimal = Decimal(0)


@dataclass
class Stopwatches:
    leader: StopwatchAPI = field(default_factory=StopwatchAPI)
    follower: StopwatchAPI = field(default_factory=StopwatchAPI)
    bridge: StopwatchAPI = field(default_factory=StopwatchAPI)


stopwatches = Stopwatches()
