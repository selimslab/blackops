from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from blackops.exchanges.base import ExchangeBase
from blackops.util.logger import logger


@dataclass
class BinanceBase(ExchangeBase):
    name: str

    fee_percent: Decimal = Decimal("0.009")

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
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

        try:
            best_ask = book.get("data", {}).get("a")
            if best_ask:
                return Decimal(best_ask)
            return None
        except Exception as e:
            logger.info(e)
            return None

    def get_mid(self, book: dict) -> Optional[Decimal]:
        best_bid = self.get_best_bid(book)
        best_ask = self.get_best_ask(book)

        if not best_bid or not best_ask:
            return None

        mid = (best_bid + best_ask) / Decimal("2")

        return mid