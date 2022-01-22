from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.periodic import StopwatchAPI


@dataclass
class Window:
    sell: Optional[Decimal] = None
    buy: Optional[Decimal] = None


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class CreditBPS:
    sell: Decimal = Decimal(0)
    hold: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


@dataclass
class Credits:
    taker: CreditBPS = field(default_factory=CreditBPS)


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
