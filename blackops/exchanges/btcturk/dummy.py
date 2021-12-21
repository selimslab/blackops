import asyncio
import collections
import random
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.btcturk.base import AssetBalance, Order
from blackops.util.logger import logger


@dataclass
class BtcturkDummy:
    balances: Dict[str, AssetBalance] = field(default_factory=dict)

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee = Decimal("1") + fee_percent
    sell_with_fee = Decimal("1") - fee_percent

    open_bids: dict = field(default_factory=dict)
    open_asks: dict = field(default_factory=dict)
    all_orders: list = field(default_factory=list)

    async def get_account_balance(self) -> dict:
        return {"data": [asdict(balance) for balance in self.balances.values()]}

    def add_balance(self, symbol: str, val: Decimal):
        if symbol in self.balances:
            self.balances[symbol].free += val
        else:
            self.balances[symbol] = AssetBalance(symbol, free=val)

    def subtract_balance(self, symbol: str, val: Decimal):
        if symbol in self.balances:
            self.balances[symbol].free -= val
        else:
            self.balances[symbol] = AssetBalance(symbol, free=val)

    async def get_open_orders(self, symbol: str) -> Optional[dict]:
        return {
            "bids": list(self.open_bids.values()),
            "asks": list(self.open_asks.values()),
        }

    async def buy(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):
        quote_balance = self.balances.get(
            pair.quote.symbol, AssetBalance(pair.quote.symbol)
        ).free

        cost = Decimal(quantity) * Decimal(price) * self.buy_with_fee
        if quote_balance < cost:
            return {
                "success": False,
                "message": f"Insufficient funds: have {quote_balance} {pair.quote.symbol} but need {cost}",
            }

        order_id = str(random.randint(1, 1000000))
        open_order = {"id": order_id, "leftAmount": quantity, "type": order_type}

        self.open_bids[order_id] = open_order
        await asyncio.sleep(0.2)  # 300 limit

        self.subtract_balance(pair.quote.symbol, cost)
        self.add_balance(pair.base.symbol, Decimal(quantity))

        order = {
            "success": True,
            "data": {
                "id": order_id,
                "datetime": time.time() * 1000,
                "price": price,
                "quantity": quantity,
                "type": order_type,
                "pairSymbol": pair.symbol,
            },
        }

        del self.open_bids[order_id]
        self.all_orders.append(order)

        return order

    async def sell(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):
        base_balance = self.balances.get(
            pair.base.symbol, AssetBalance(pair.base.symbol)
        ).free

        if base_balance < quantity:
            return {
                "success": False,
                "message": f"Insufficient funds: have {base_balance} {pair.base.symbol} but need {quantity}",
            }

        order_id = str(random.randint(1, 1000000))
        open_order = {"id": order_id, "leftAmount": quantity, "type": order_type}

        self.open_asks[order_id] = open_order
        await asyncio.sleep(0.2)  # 300 limit

        self.subtract_balance(pair.base.symbol, Decimal(quantity))
        self.add_balance(
            pair.quote.symbol,
            Decimal(quantity) * Decimal(price) * self.sell_with_fee,
        )

        order = {
            "success": True,
            "data": {
                "id": order_id,
                "datetime": time.time() * 1000,
                "price": price,
                "quantity": quantity,
                "type": order_type,
                "pairSymbol": pair.symbol,
            },
        }

        del self.open_asks[order_id]
        self.all_orders.append(order)

        return order

    async def process_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):
        if order_type == "buy":
            return await self.buy(pair, order_type, price, quantity)
        elif order_type == "sell":
            return await self.sell(pair, order_type, price, quantity)
