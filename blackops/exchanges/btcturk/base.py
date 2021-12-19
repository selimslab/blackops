import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from blackops.exchanges.base import ExchangeBase
from blackops.util.logger import logger


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


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


def test_btc_base():

    book = {
        "AO": [
            {"P": "15.3"},
            {"P": "14.9"},
            {"P": "15.5"},
            {"P": "15.7"},
        ],
        "BO": [
            {"P": "15.3"},
            {"P": "14.9"},
            {"P": "15.5"},
            {"P": "15.7"},
        ],
    }
    client = BtcturkBase()

    ask = client.get_best_ask(book)
    assert ask == Decimal("14.9")

    bid = client.get_best_bid(book)
    assert bid == Decimal("15.7")


if __name__ == "__main__":
    test_btc_base()
