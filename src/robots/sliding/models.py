from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.periodic import StopwatchAPI


@dataclass
class Theo:
    sell: Decimal = Decimal(0)
    mid: Decimal = Decimal(0)
    usdt: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)
    std: Decimal = Decimal(0)


@dataclass
class BookTop:
    ask: Optional[Decimal] = None
    bid: Optional[Decimal] = None

    @property
    def mid(self):
        return (self.ask + self.bid) / Decimal(2)


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
