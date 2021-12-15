from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class ExchangeBase(ABC):
    name: str
