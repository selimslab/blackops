import asyncio
import collections
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from blackops.util.logger import logger


@dataclass
class BtcturkDummy:
    balances: Dict[str, Decimal] = field(
        default_factory=lambda: collections.defaultdict(Decimal)
    )

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee = Decimal("1") + fee_percent
    sell_with_fee = Decimal("1") - fee_percent

    async def get_account_balance(self, assets: Optional[List[str]]) -> List[dict]:
        if assets:
            return [{"free": self.balances[symbol]} for symbol in assets]
        else:
            return [
                {"free": balance, "asset": symbol}
                for symbol, balance in self.balances.items()
            ]

    async def set_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] = val

    async def add_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] += val

    async def subtract_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] -= val

    async def process_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        await asyncio.sleep(0.2)  # 300 limit
        (base, quote) = pair_symbol.split("_")

        balance_list = await self.get_account_balance([base, quote])
        decimal_balances = [
            Decimal(asset.get("balance", "0")) for asset in balance_list
        ]
        base_balance, quote_balance = decimal_balances

        if order_type == "buy":
            cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
            if quote_balance < cost:
                raise ValueError("Insufficient funds")
            await self.add_balance(base, Decimal(quantity))
            await self.subtract_balance(quote, cost)

        elif order_type == "sell":
            if base_balance < quantity:
                raise ValueError("Insufficient funds")
            await self.subtract_balance(base, Decimal(quantity))
            await self.add_balance(
                quote, Decimal(quantity) * Decimal(price) * self.sell_with_fee
            )
