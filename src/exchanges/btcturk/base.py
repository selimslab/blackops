import asyncio
import itertools
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

import aiohttp

from src.domain import Asset
from src.domain.models import AssetPair
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import lock_with_timeout


@dataclass
class BtcturkBase(ExchangeAPIClientBase):

    api_key: str = "no key"
    api_secret: str = "no secret"

    session: Optional[aiohttp.ClientSession] = None

    async def activate_rate_limit(self) -> None:
        async with lock_with_timeout(
            self.locks.rate_limit, sleep_seconds.rate_limit
        ) as ok:
            if ok:
                await self._close_session()
                if not self.session or self.session.closed:
                    self.session = aiohttp.ClientSession()

    @staticmethod
    def parse_prices(orders: List[dict]) -> list:
        if not orders:
            return []
        try:
            return [Decimal(order["P"]) for order in orders]
        except Exception as e:
            return []

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        if not book:
            return None

        prices = BtcturkBase.parse_prices(book.get("BO", []))
        if prices:
            return max(prices)

        return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        if not book:
            return None

        prices = BtcturkBase.parse_prices(book.get("AO", []))
        if prices:
            return min(prices)

        return None

    @staticmethod
    def parse_account_balance(res: dict, symbols: Optional[List[str]] = None) -> dict:
        balance_list = res.get("data", [])
        if not balance_list:
            return {}

        # btc calls asset, we call symbol
        try:
            balance_dict = {
                balance_info["asset"]: balance_info for balance_info in balance_list
            }
        except KeyError:
            balance_dict = {
                balance_info["symbol"]: balance_info for balance_info in balance_list
            }

        try:
            if symbols:
                # init unexisting symbols
                for symbol in symbols:
                    if symbol not in balance_dict:
                        balance_dict[symbol] = Asset(symbol=symbol).dict()

                return {
                    symbol: balance_info
                    for symbol, balance_info in balance_dict.items()
                    if symbol in symbols
                }
            else:
                return balance_dict
        except Exception as e:
            logger.error(f"get_account_balance: {e}")
            raise e

    @staticmethod
    def parse_open_orders(open_orders: dict) -> Tuple[list, list]:
        if not open_orders:
            return ([], [])

        data = open_orders.get("data", {})
        open_asks = data.get("asks", [])
        open_bids = data.get("bids", [])

        return (open_asks, open_bids)

    def get_sorted_order_list(self, order_res: dict):
        if not order_res:
            return []

        (
            sell_orders,
            buy_orders,
        ) = self.parse_open_orders(order_res)

        if sell_orders or buy_orders:
            orders = [
                x
                for lst in itertools.zip_longest(buy_orders, sell_orders)
                for x in lst
                if x
            ]
            return orders

        return []

    async def cancel_open_orders(self, pair: AssetPair) -> list:
        res: Optional[dict] = await self.get_open_orders(pair)
        if res:
            orders = self.get_sorted_order_list(res)
            await self.cancel_multiple_orders(orders)

        return []

    async def cancel_multiple_orders(self, orders: list) -> list:
        if not orders:
            return []

        order_ids = [order.get("id") for order in orders]
        order_ids = [i for i in order_ids if i]

        cancelled = []
        if len(order_ids) == 1:
            await asyncio.sleep(0.04)  # allow 30 ms for order to be filled
        for order_id in order_ids:
            ok = await self.cancel_order(order_id)
            if ok:
                cancelled.append(order_id)
            await asyncio.sleep(sleep_seconds.cancel_wait)
            await asyncio.sleep(0.01)  #  allow others to cancel too
        return cancelled

    @staticmethod
    def parse_submit_order_response(res: dict):
        data = res.get("data", {})

        order_id = data.get("id")

        ts = data.get("datetime")
        order_time = datetime.fromtimestamp(ts / 1000.0)

        return order_time

    async def _close_session(self):
        if self.session:
            await self.session.close()
