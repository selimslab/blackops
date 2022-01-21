from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .models import Credits, Signals, Window


@dataclass
class Stats:
    start_time: datetime = field(default_factory=lambda: datetime.now())
    taker: Window = field(default_factory=Window)
    signals: Signals = field(default_factory=Signals)
    current_step: Decimal = Decimal("0")
    credits: Credits = field(default_factory=Credits)
