import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from blackops.exchanges.base import ExchangeBase
from blackops.util.logger import logger


@dataclass
class BtcturkBase(ExchangeBase):

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee = Decimal("1") + fee_percent
    sell_with_fee = Decimal("1") - fee_percent

    @staticmethod
    def parse_book(book: str) -> dict:
        try:
            return json.loads(book)[1]
        except Exception as e:
            logger.info(e)
            return {}

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        purchase_orders = book.get("BO", [])
        if purchase_orders:
            prices = [order.get("P") for order in purchase_orders]
            prices = [Decimal(price) for price in prices if price]
            return max(prices)
        return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        sales_orders = book.get("AO", [])
        if sales_orders:
            prices = [order.get("P") for order in sales_orders]
            prices = [Decimal(price) for price in prices if price]
            return min(prices)
        return None
