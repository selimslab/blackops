import asyncio
import collections
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

        balance_list = await self.get_account_balance(
            [pair.base.symbol, pair.quote.symbol]
        )
        decimal_balances = [
            Decimal(asset.get("balance", "0")) for asset in balance_list
        ]
        base_balance, quote_balance = decimal_balances

        if order_type == "buy":
            cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
            if quote_balance < cost:
                raise ValueError("Insufficient funds")
            await self.add_balance(pair.base.symbol, Decimal(quantity))
            await self.subtract_balance(pair.quote.symbol, cost)

        elif order_type == "sell":
            if base_balance < quantity:
                raise ValueError("Insufficient funds")
            await self.subtract_balance(pair.base.symbol, Decimal(quantity))
            await self.add_balance(
                pair.quote.symbol,
                Decimal(quantity) * Decimal(price) * self.sell_with_fee,
            )
