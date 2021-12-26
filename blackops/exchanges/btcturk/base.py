import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

import simplejson as json  # type: ignore

from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.btcturk.models import (
    AccountBalanceResponse,
    OpenOrdersData,
    OpenOrdersResponse,
    OrderData,
    OrderType,
    SubmitOrderResponse,
)
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

    @staticmethod
    def parse_prices(orders: List[dict]) -> list:
        if not orders:
            return []

        str_prices = [
            order.get("P") for order in orders if order and isinstance(order, dict)
        ]
        prices = [Decimal(price) for price in str_prices if price]
        return prices

    @staticmethod
    def get_best_bid(book: dict) -> Optional[Decimal]:
        if not book:
            return None

        purchase_orders = book.get("BO", [])
        prices = BtcturkBase.parse_prices(purchase_orders)
        if prices:
            return max(prices)

        return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        if not book:
            return None

        sales_orders = book.get("AO", [])
        prices = BtcturkBase.parse_prices(sales_orders)
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

    async def cancel_multiple_orders(self, orders: list) -> None:
        if not orders:
            return None

        order_ids = [order.get("id") for order in orders]
        order_ids = [i for i in order_ids if i]
        for order_id in order_ids:
            await self.cancel_order(order_id)
            await asyncio.sleep(0.1)

    @staticmethod
    def parse_submit_order_response(res: dict):
        data = res.get("data", {})

        order_id = data.get("id")

        ts = data.get("datetime")
        order_time = datetime.fromtimestamp(ts / 1000.0)

        return order_time

    async def _close_session(self):
        pass

    # async def cancel_open_orders(self, pair: AssetPair, bids=True, asks=True):
    #     """
    #     we need order ids

    #     either read from the saved

    #     or get open orders
    #     """
    #     res = await self.get_open_orders(pair)
    #     if not res:
    #         return

    #     data = res.get("data", {})
    #     asks = data.get("asks", [])
    #     bids = data.get("bids", [])

    #     results = []
    #     if bids:
    #         for order in bids:
    #             order_id = order.get("id")
    #             res = await self.cancel_order(order_id)
    #             results.append(res)

    #     if asks:
    #         for order in asks:
    #             order_id = order.get("id")
    #             res = await self.cancel_order(order_id)
    #             results.append(res)

    #     return results


def test_btc_base():

    book = {
        "AO": [
            {"P": "15.3"},
            {"P": "14.9"},
            {"P": "15.5"},
            {"P": "15.7"},
        ],
        "BO": [
            {"P": "15.3"},
            {"P": "14.9"},
            {"P": "15.5"},
            {"P": "15.7"},
        ],
    }
    client = BtcturkBase()

    ask = client.get_best_ask(book)
    assert ask == Decimal("14.9")

    bid = client.get_best_bid(book)
    assert bid == Decimal("15.7")


if __name__ == "__main__":
    test_btc_base()
