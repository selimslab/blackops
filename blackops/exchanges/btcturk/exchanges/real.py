from dataclasses import dataclass
from decimal import Decimal

from blackops.domain.models.asset import Asset, AssetPair
from blackops.util.logger import logger

from .base import BtcturkBase


@dataclass
class BtcturkReal(BtcturkBase):

    name = "btcturk_real"

    # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we
    # sell
    fee_percent = Decimal("0.0018")

    def __post_init__(self):
        self.buy_with_fee = Decimal(1) + self.fee_percent
        self.sell_with_fee = Decimal(1) - self.fee_percent

    async def long(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed"""

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="buy",
            pair_symbol=symbol,
        )

        logger.info(f"buy order for {qty} {symbol} at {price}")

    async def short(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed after we deliver"""

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="sell",
            pair_symbol=symbol,
        )

        logger.info(f"sell order for {qty} {symbol} at {price}")
