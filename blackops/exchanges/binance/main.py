from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from blackops.domain.models import Asset, AssetPair, Exchange, LeaderFollowerStrategy
from blackops.util.logger import logger
from blackops.util.numbers import decimal_division, decimal_mid

from .streams import binance_stream_generator


@dataclass
class Binance(Exchange):
    name: str = "binance"

    @staticmethod
    def get_mid(order_book: dict) -> Optional[Decimal]:
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

    @staticmethod
    async def book_ticker_stream(symbol: str):
        async for book in binance_stream_generator(symbol, "@bookTicker"):
            yield book
