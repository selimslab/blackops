import collections
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from beartype import beartype


@dataclass
class BtcturkTestnetApiClient:
    fee_percent: Decimal = Decimal("0.0018")
    balances: Dict[str, Decimal] = field(
        default_factory=lambda: collections.defaultdict(Decimal)
    )

    def __post_init__(self):
        self.buy_with_fee = Decimal(1) + self.fee_percent
        self.sell_with_fee = Decimal(1) - self.fee_percent

    async def set_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] = val

    async def get_balance(self, symbol: str) -> Optional[Decimal]:
        return self.balances.get(symbol, Decimal(0))

    async def get_account_balance(self, assets: List[str]) -> List[dict]:
        return [{"balance": self.balances[symbol]} for symbol in assets]

    async def add_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] += val

    async def subtract_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] -= val

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        (base, quote) = pair_symbol.split("_")

        if order_type == "buy":
            await self.add_balance(base, Decimal(quantity))
            await self.subtract_balance(
                quote, Decimal(quantity) * Decimal(price) * self.buy_with_fee
            )
        elif order_type == "sell":
            await self.subtract_balance(base, Decimal(quantity))
            await self.add_balance(
                quote, Decimal(quantity) * Decimal(price) * self.sell_with_fee
            )
