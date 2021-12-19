import asyncio
import collections
import random
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from blackops.domain.asset import Asset, AssetPair
from blackops.util.logger import logger


@dataclass
class BtcturkDummy:
    balances: Dict[str, Decimal] = field(
        default_factory=lambda: collections.defaultdict(Decimal)
    )

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee = Decimal("1") + fee_percent
    sell_with_fee = Decimal("1") - fee_percent

    async def get_account_balance(self, assets: Optional[List[str]]) -> dict:

        all_balances = {
            asset: {"free": balance, "locked": 0}
            for asset, balance in self.balances.items()
        }

        if assets:
            for asset in assets:
                if asset not in all_balances:
                    all_balances[asset] = {"free": 0, "locked": 0}

            return {
                asset: balance
                for asset, balance in all_balances.items()
                if asset in assets
            }
        else:
            return all_balances

    async def add_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] += val

    async def subtract_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] -= val

    async def process_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):
        await asyncio.sleep(0.2)  # 300 limit

        balances = await self.get_account_balance([pair.base.symbol, pair.quote.symbol])

        base_balances: dict = balances[pair.base.symbol]
        base_balance = Decimal(base_balances["free"]) + Decimal(base_balances["locked"])

        quote_balances: dict = balances[pair.quote.symbol]
        quote_balance = Decimal(quote_balances["free"]) + Decimal(
            quote_balances["locked"]
        )

        if order_type == "buy":
            cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
            if quote_balance < cost:
                return {
                    "success": False,
                    "message": f"Insufficient funds: {quote_balance} < {cost}",
                }
            await self.add_balance(pair.base.symbol, Decimal(quantity))
            await self.subtract_balance(pair.quote.symbol, cost)
            return {
                "success": True,
                "data": {
                    "id": str(random.randint(1, 1000000)),
                    "datetime": int(time.time()),
                },
            }

        elif order_type == "sell":
            if base_balance < quantity:
                return {
                    "success": False,
                    "message": f"Insufficient funds: {base_balance} < {quantity}",
                }
            await self.subtract_balance(pair.base.symbol, Decimal(quantity))
            await self.add_balance(
                pair.quote.symbol,
                Decimal(quantity) * Decimal(price) * self.sell_with_fee,
            )
            return {
                "success": True,
                "data": {
                    "id": str(random.randint(1, 1000000)),
                    "datetime": int(time.time()),
                },
            }
