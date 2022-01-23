from abc import ABC
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Tuple

from src.domain import Asset, AssetPair
from src.domain.models import OrderType
from src.exchanges.locks import Locks


@dataclass
class ExchangeAPIClientBase(ABC):
    name: Optional[str] = None
    locks: Locks = field(default_factory=Locks)

    orders_in_last_second: int = 0
    max_orders_per_second: int = 6

    async def clear_orders_in_last_second(self):
        self.orders_in_last_second = 0

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

        return (best_bid + best_ask) / Decimal("2")

    async def submit_limit_order(
        self, pair: AssetPair, side: OrderType, price: float, quantity: float
    ) -> Optional[dict]:
        pass

    async def get_open_orders(self, pair: AssetPair) -> Optional[dict]:
        """
        new in the bottom of the page
        """

    async def cancel_order(self, order_id: int) -> Optional[dict]:
        pass

    async def cancel_multiple_orders(self, orders: list) -> list:
        return []

    async def cancel_open_orders(self, pair: AssetPair) -> list:
        return []

    def get_sorted_order_list(self, order_res: dict):
        pass
