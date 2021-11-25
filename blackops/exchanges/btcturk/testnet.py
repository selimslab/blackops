import asyncio
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

    async def get_balance(self, symbol: str) -> Decimal:
        await asyncio.sleep(0.7)  # 90 limit
        return self.balances.get(symbol, Decimal(0))

    async def get_account_balance(self, assets: List[str]) -> List[dict]:
        await asyncio.sleep(0.7)
        return [{"balance": self.balances[symbol]} for symbol in assets]

    async def add_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] += val

    async def subtract_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] -= val

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        await asyncio.sleep(0.2)  # 300 limit
        (base, quote) = pair_symbol.split("_")

        if order_type == "buy":
            cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
            quote_balance = await self.get_balance(quote)
            if quote_balance < cost:
                raise ValueError("Insufficient funds")
            await self.add_balance(base, Decimal(quantity))
            await self.subtract_balance(quote, cost)

        elif order_type == "sell":
            base_balance = await self.get_balance(base)
            if base_balance < quantity:
                raise ValueError("Insufficient funds")
            await self.subtract_balance(base, Decimal(quantity))
            await self.add_balance(
                quote, Decimal(quantity) * Decimal(price) * self.sell_with_fee
            )
