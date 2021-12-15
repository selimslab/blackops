import asyncio
import collections
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from blackops.util.logger import logger

from .base import BtcturkBase


@dataclass
class BtcturkDummy:
    balances: Dict[str, Decimal] = field(
        default_factory=lambda: collections.defaultdict(Decimal)
    )

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee = Decimal("1") + fee_percent
    sell_with_fee = Decimal("1") - fee_percent

    async def get_account_balance(self, assets: List[str]) -> List[dict]:
        return [{"balance": self.balances[symbol]} for symbol in assets]

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


@dataclass
class BtcturkApiClientTestnet(BtcturkBase):
    name: str = "btcturk_testnet"

    test_exchange: BtcturkDummy = BtcturkDummy()

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        try:
            await self.test_exchange.process_limit_order(
                pair_symbol=pair_symbol,
                order_type=order_type,
                price=price,
                quantity=quantity,
            )
        except Exception as e:
            logger.error(e)
            raise e

    async def get_account_balance(self, assets: List[str]) -> List[dict]:
        await asyncio.sleep(
            0.35
        )  # simulate 180 calls per second, 90 balance, 90 orders
        return await self.test_exchange.get_account_balance(assets)
