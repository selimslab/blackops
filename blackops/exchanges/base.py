from abc import ABC
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Tuple

from blackops.domain.asset import Asset, AssetPair


@dataclass
class ExchangeAPIClientBase(ABC):
    name: Optional[str] = None

    fee_percent: Decimal = Decimal("0.0018")
    buy_with_fee: Decimal = Decimal("1") + fee_percent
    sell_with_fee: Decimal = Decimal("1") - fee_percent

    async def get_account_balance(self) -> Optional[dict]:
        pass

    @staticmethod
    def parse_account_balance(res: dict, symbols: Optional[List[str]] = None) -> dict:
        return {}

    @staticmethod
    def parse_open_orders(open_orders: dict) -> Tuple[list, list]:
        return ([], [])

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        pass

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        pass

    def get_mid(self, book: dict) -> Optional[Decimal]:
        best_bid = self.get_best_bid(book)
        best_ask = self.get_best_ask(book)

        if not best_bid or not best_ask:
            return None

        mid = (best_bid + best_ask) / Decimal("2")

        return mid

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> Optional[dict]:
        pass

    async def get_open_orders(self, pair: AssetPair) -> Optional[dict]:
        """
        new in the bottom of the page
        """

    async def cancel_order(self, order_id: int) -> Optional[dict]:
        pass

    async def cancel_multiple_orders(self, orders: list) -> None:
        pass
