from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

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
    def get_best_bid(book: dict) -> Optional[Decimal]:
        if not book:
            return None
        purchase_orders = book.get("BO", [])
        if purchase_orders:
            str_prices = [
                order.get("P")
                for order in purchase_orders
                if order and isinstance(order, dict)
            ]
            if str_prices:
                prices = [Decimal(price) for price in str_prices if price]
                return max(prices)
        return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        if not book:
            return None
        sales_orders = book.get("AO", [])
        if sales_orders:
            str_prices = [
                order.get("P")
                for order in sales_orders
                if order and isinstance(order, dict)
            ]
            if str_prices:
                prices: List[Decimal] = [
                    Decimal(price) for price in str_prices if price
                ]
                return min(prices)
        return None

    async def _get_account_balance(self) -> dict:
        raise NotImplementedError

    async def get_account_balance(self, symbols: Optional[List[str]] = None) -> dict:
        res = await self._get_account_balance()
        if not res or not isinstance(res, dict):
            raise Exception("Could not get account balance")

        balance_list = res.get("data", [])

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

    async def get_open_orders(self, pair: AssetPair) -> Optional[dict]:
        """
        new in the bottom of the page
        """
        raise NotImplementedError

    async def get_open_asks_and_bids(self, pair: AssetPair) -> tuple:
        open_orders: Optional[dict] = await self.get_open_orders(pair)

        open_ask_amount: Decimal = Decimal("0")
        open_bid_amount: Decimal = Decimal("0")
        open_bids: list = []
        open_asks: list = []

        if open_orders:
            data = open_orders.get("data", {})
            open_bids = data.get("bids", [])
            open_asks = data.get("asks", [])

            if open_asks:
                open_ask_amount = Decimal(
                    sum(
                        Decimal(ask.get("leftAmount", "0"))
                        for ask in open_asks
                        if ask and isinstance(ask, dict)
                    )
                )
            if open_bids:
                open_bid_amount = Decimal(
                    sum(
                        Decimal(bid.get("leftAmount", "0"))
                        for bid in open_bids
                        if bid and isinstance(bid, dict)
                    )
                )

        return (open_asks, open_bids, open_ask_amount, open_bid_amount)

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
