from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.periodic import StopwatchAPI


@dataclass
class PriceWindow:
    buy: Decimal = Decimal(0)
    sell: Decimal = Decimal(0)


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


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
