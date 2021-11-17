import collections
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from beartype import beartype

from blackops.util.logger import logger

from .base import BtcturkBase


@beartype
@dataclass
class BtcturkTestnet(BtcturkBase):

    name = "btcturk_testnet"

    def __post_init__(self):
        self.balances = field(default_factory=lambda: collections.defaultdict(Decimal))

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

    def get_balance_multiple(self, symbols: list) -> List[Decimal]:
        try:
            res_list = self.api_client.get_account_balance(assets=symbols)
            decimal_balances = [Decimal(r.get("balance")) for r in res_list]
            return decimal_balances
        except Exception as e:
            logger.info(f"could not read balances: {e}")
            return []

    def get_balance(self, symbol: str) -> Optional[Decimal]:
        balance_list = self.get_balance_multiple([symbol])
        if balance_list:
            return balance_list[0]
        return None
