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

    open_orders: dict = field(default_factory=dict)
    all_orders: list = field(default_factory=list)

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

    def add_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] += val

    def subtract_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] -= val

    async def get_open_orders(self, symbol: str) -> Optional[dict]:
        return {
            "bids": [
                order for order in self.open_orders.values() if order["type"] == "buy"
            ],
            "asks": [
                order for order in self.open_orders.values() if order["type"] == "sell"
            ],
        }

    async def process_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):

        balances = await self.get_account_balance([pair.base.symbol, pair.quote.symbol])

        base_balances: dict = balances[pair.base.symbol]
        base_balance = Decimal(base_balances["free"]) + Decimal(base_balances["locked"])

        quote_balances: dict = balances[pair.quote.symbol]
        quote_balance = Decimal(quote_balances["free"]) + Decimal(
            quote_balances["locked"]
        )

        order_id = str(random.randint(1, 1000000))
        open_order = {"id": order_id, "leftAmount": quantity, "type": order_type}

        if order_type == "buy":
            cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
            if quote_balance < cost:
                return {
                    "success": False,
                    "message": f"Insufficient funds: {quote_balance} < {cost}",
                }

            self.open_orders[order_id] = open_order
            await asyncio.sleep(0.2)  # 300 limit

            self.subtract_balance(pair.quote.symbol, cost)
            self.add_balance(pair.base.symbol, Decimal(quantity))
            self.subtract_balance(pair.quote.symbol, cost)

            order = {
                "success": True,
                "data": {
                    "id": str(random.randint(1, 1000000)),
                    "datetime": int(time.time()),
                    "price": price,
                    "quantity": quantity,
                    "type": order_type,
                    "pairSymbol": pair.symbol,
                },
            }

            del self.open_orders[order_id]
            self.all_orders.append(order)

            return order

        elif order_type == "sell":
            if base_balance < quantity:
                return {
                    "success": False,
                    "message": f"Insufficient funds: {base_balance} < {quantity}",
                }

            self.open_orders[order_id] = open_order
            await asyncio.sleep(0.2)  # 300 limit

            self.subtract_balance(pair.base.symbol, Decimal(quantity))
            self.add_balance(
                pair.quote.symbol,
                Decimal(quantity) * Decimal(price) * self.sell_with_fee,
            )

            order = {
                "success": True,
                "data": {
                    "id": str(random.randint(1, 1000000)),
                    "datetime": int(time.time()),
                    "price": price,
                    "quantity": quantity,
                    "type": order_type,
                    "pairSymbol": pair.symbol,
                },
            }

            del self.open_orders[order_id]
            self.all_orders.append(order)
