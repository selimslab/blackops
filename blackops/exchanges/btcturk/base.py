import json
from dataclasses import dataclass
from decimal import Decimal

from blackops.domain.models.exchange import ExchangeBase
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

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        raise NotImplementedError

    async def long(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed"""
        await self.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="buy",
            pair_symbol=symbol,
        )

    async def short(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed after we deliver"""
        await self.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="sell",
            pair_symbol=symbol,
        )
