from decimal import Decimal
from typing import Optional

from blackops.util.logger import logger
from blackops.util.numbers import decimal_mid


def get_binance_book_mid(order_book: dict) -> Optional[Decimal]:
    """get mid price from binance orderbook"""
    if not order_book:
        return None

    try:
        order_book = order_book.get("data", {})

        best_ask_price = order_book.get("a", 0)
        best_bid_price = order_book.get("b", 0)

        return decimal_mid(best_ask_price, best_bid_price)

    except Exception as e:
        logger.info(e)
        return None
