import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Optional

from blackops.domain.models.exchange import ExchangeBase
from blackops.util.logger import logger


@dataclass
class BtcturkBase(ExchangeBase):

    api_client: Any = None

    name: str = "btcturk"

    # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we
    # sell
    fee_percent = Decimal(0.0018)

    # if connection is lost, we reset these two, should we? probably yes
    best_seller = Decimal("inf")
    best_buyer = Decimal("-inf")

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

    @classmethod
    async def get_balance_multiple(cls, symbols: list) -> List[Decimal]:
        try:
            res_list = await cls.api_client.get_account_balance(assets=symbols)
            decimal_balances = [Decimal(r.get("balance")) for r in res_list]
            return decimal_balances
        except Exception as e:
            logger.info(f"could not read balances: {e}")
            return []

    @classmethod
    async def get_balance(cls, symbol: str) -> Optional[Decimal]:
        balance_list = await cls.get_balance_multiple([symbol])
        if balance_list:
            return balance_list[0]
        return None
