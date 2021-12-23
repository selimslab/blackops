from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from blackops.domain.asset import Asset, AssetPair


@dataclass
class ExchangeBase(ABC):
    name: Optional[str] = None

    async def get_account_balance(self, symbols: Optional[List[str]] = None):
        raise NotImplementedError

    @staticmethod
    def parse_book(book: str) -> dict:
        raise NotImplementedError

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        raise NotImplementedError

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        raise NotImplementedError

    def get_mid(self, book: dict) -> Optional[Decimal]:
        """Get mid of bid and ask"""
        raise NotImplementedError

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> Optional[dict]:
        raise NotImplementedError

    async def cancel_order(self, order_id: int) -> Optional[dict]:
        raise NotImplementedError

    async def get_open_orders(self, pair: AssetPair) -> Optional[dict]:
        """
        new in the bottom of the page
        """
        raise NotImplementedError

    def parse_open_orders(self, open_orders: dict) -> Tuple[list, list]:
        raise NotImplementedError
