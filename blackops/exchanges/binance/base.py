from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from blackops.domain.models.exchange import ExchangeBase
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
