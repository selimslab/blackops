from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .models import Credits, Prices, Signals, TargetPrices


@dataclass
class Stats:
    start_time: datetime = field(default_factory=lambda: datetime.now())

    current_step: Decimal = Decimal("0")

    credits: Credits = field(default_factory=Credits)
    signals: Signals = field(default_factory=Signals)
    prices: TargetPrices = field(default_factory=TargetPrices)
