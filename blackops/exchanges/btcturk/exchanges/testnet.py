import collections
from dataclasses import dataclass, field
from decimal import Decimal

from beartype import beartype

from blackops.util.logger import logger

from .base import BtcturkBase


@dataclass
class BtcturkTestnet(BtcturkBase):

    name = "btcturk_testnet"
    fee_percent: Decimal = Decimal("0.0018")

    def __post_init__(self):
        self.balances: collections.defaultdict = collections.defaultdict(Decimal)
        self.buy_with_fee = Decimal(1) + self.fee_percent
        self.sell_with_fee = Decimal(1) - self.fee_percent

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
