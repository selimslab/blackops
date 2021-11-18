import json
from dataclasses import dataclass
from decimal import Decimal
from typing import AsyncIterator, List, Optional

from beartype import beartype

from blackops.domain.models import Asset, AssetPair, Exchange
from blackops.util.logger import logger
from blackops.util.numbers import decimal_division, decimal_mid

from .base import BtcturkBase
from .streams import create_book_stream


@dataclass
class BtcturkReal(BtcturkBase):

    name = "btcturk_real"

    # we pay Decimal(1 + 0.0018) to buy, we get Decimal(1 - 0.0018) when we
    # sell
    fee_percent = Decimal(0.0018)
    buy_with_fee = Decimal(1 + fee_percent)
    sell_with_fee: Decimal = Decimal(1 - fee_percent)

    def __post_init__(self):
        ...

    def get_balance_multiple(self, symbols: list) -> List[Decimal]:
        try:
            res_list = self.api_client.get_account_balance(assets=symbols)
            decimal_balances = [Decimal(r.get("balance")) for r in res_list]
            return decimal_balances
        except Exception as e:
            logger.info(f"could not read balances: {e}")
            return []

    def get_balance(self, symbol: str) -> Optional[Decimal]:
        balance_list = self.get_balance_multiple([symbol])
        if balance_list:
            return balance_list[0]
        return None

    async def long(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed"""

        logger.info(f"buying {qty} {symbol} at {price}")

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="buy",
            pair_symbol=symbol,
        )

    async def short(self, price: float, qty: float, symbol: str):
        """the order may or may not be executed"""

        logger.info(f"selling {qty} {symbol} at {price}")

        await self.api_client.submit_limit_order(
            quantity=float(qty),
            price=float(price),
            order_type="sell",
            pair_symbol=symbol,
        )

    def calculate_pnl(
        self, pair: AssetPair, start_quote_balance: Decimal
    ) -> Optional[Decimal]:
        try:
            base_balance, quote_balance = self.get_balance_multiple(
                [pair.base.symbol, pair.quote.symbol]
            )
            approximate_sales_gain: Decimal = (
                base_balance * self.best_buyer * self.sell_with_fee
            )
            return quote_balance + approximate_sales_gain - start_quote_balance
        except Exception as e:
            logger.info(e)
            return None

    async def orderbook_stream(self, symbol: str) -> AsyncIterator[dict]:
        async for book in create_book_stream(symbol):
            if book:
                yield self.parse_orderbook(book)
