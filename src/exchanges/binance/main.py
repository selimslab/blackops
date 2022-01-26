from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger


@dataclass
class BinanceBase(ExchangeAPIClientBase):
    name: str = "Binance"

    @staticmethod
    def get_mid(book: dict) -> Optional[Decimal]:
        if book:
            data = book.get("data", {})
            return (Decimal(data.get("a")) + Decimal(data.get("b"))) / Decimal(2)
        return None

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        if not book:
            return None
        try:
            best_bid = book.get("data", {}).get("b")
            if best_bid:
                return Decimal(best_bid)
            return None
        except Exception as e:
            logger.info(e)
            return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        if not book:
            return None
        try:
            best_ask = book.get("data", {}).get("a")
            if best_ask:
                return Decimal(best_ask)
            return None
        except Exception as e:
            logger.info(e)
            return None
