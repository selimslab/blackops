import collections
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from blackops.util.logger import logger

from .main import Btcturk


@dataclass
class BtcturkTestClient(Btcturk):
    def __post_init__(self):
        self.balances = field(default_factory=lambda: collections.defaultdict(Decimal))

    def set_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] = val

    def get_balance(self, symbol: str) -> Optional[Decimal]:
        return self.balances.get(symbol, Decimal(0))

    async def short(self, price: float, qty: float, symbol: str):

        logger.info(f"selling {qty} {symbol} at {price}..")

        (base, quote) = symbol.split("_")

        gross = Decimal(qty) * Decimal(price) * self.sell_with_fee

        self.balances[base] -= Decimal(qty)
        self.balances[quote] += gross

    async def long(self, price: float, qty: float, symbol: str):

        logger.info(f"buying {qty} {symbol} at {price}..")

        (base, quote) = symbol.split("_")

        cost = Decimal(qty * price) * self.buy_with_fee

        self.balances[base] += Decimal(qty)
        self.balances[quote] -= cost
