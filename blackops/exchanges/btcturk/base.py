import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from blackops.domain.models import Exchange
from blackops.util.logger import logger


@dataclass
class BtcturkBase(Exchange):

    api_client: Any = None

    name: str = "btcturk"

    # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we
    # sell
    fee_percent = Decimal(0.0018)
    buy_with_fee = Decimal(1 + fee_percent)
    sell_with_fee: Decimal = Decimal(1 - fee_percent)

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
    def parse_orderbook(orderbook: str) -> dict:
        try:
            return json.loads(orderbook)[1]
        except Exception as e:
            logger.info(e)
            return {}
