from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.periodic import StopwatchAPI


@dataclass
class PriceWindow:
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


@dataclass
class MarketPrices:
    ask: Optional[Decimal] = None
    bid: Optional[Decimal] = None


@dataclass
class Signals:
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


@dataclass
class Stopwatches:
    leader: StopwatchAPI = field(default_factory=StopwatchAPI)
    follower: StopwatchAPI = field(default_factory=StopwatchAPI)
    bridge: StopwatchAPI = field(default_factory=StopwatchAPI)


stopwatches = Stopwatches()
