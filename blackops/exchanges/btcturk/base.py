import json
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Union

from blackops.domain.models.exchange import ExchangeBase
from blackops.util.logger import logger

from .real import RealApiClient
from .testnet import BtcturkTestnetApiClient


@dataclass
class BtcturkBase(ExchangeBase):

    api_client: Union[BtcturkTestnetApiClient, RealApiClient]

    # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we
    # sell

    best_seller: Decimal = Decimal("inf")
    best_buyer: Decimal = Decimal("-inf")

    @staticmethod
    def get_sales_orders(orders: dict) -> list:
        return orders.get("AO", [])

    @staticmethod
    def get_purchase_orders(orders: dict) -> list:
        return orders.get("BO", [])

    @staticmethod
    def parse_book(book: str) -> dict:
        try:
            return json.loads(book)[1]
        except Exception as e:
            logger.info(e)
            return {}

    async def get_balance_multiple(self, symbols: list) -> List[Decimal]:
        try:
            res_list = await self.api_client.get_account_balance(assets=symbols)
            decimal_balances = [Decimal(r.get("balance", "")) for r in res_list]
            return decimal_balances
        except Exception as e:
            logger.info(f"could not read balances: {e}")
            return []

    async def get_balance(self, symbol: str) -> Optional[Decimal]:
        balance_list = await self.get_balance_multiple([symbol])
        if balance_list:
            return balance_list[0]
        return None

    async def long(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed"""

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="buy",
            pair_symbol=symbol,
        )

        logger.info(f"buy {qty} {symbol} at {price}")

    async def short(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed after we deliver"""

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="sell",
            pair_symbol=symbol,
        )

        logger.info(f"sell {qty} {symbol} at {price}")
