import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from blackops.exchanges.base import ExchangeBase
from blackops.util.logger import logger


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class AssetBalance:
    asset: str
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")


@dataclass
class Order:
    id: str
    leftAmount: str
    price: str
    quantity: str
    order_type: str


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
        purchase_orders = book.get("BO", [])
        if purchase_orders:
            prices = [order.get("P") for order in purchase_orders]
            prices = [Decimal(price) for price in prices if price]
            return max(prices)
        return None

    @staticmethod
    def get_best_ask(book: dict) -> Optional[Decimal]:
        sales_orders = book.get("AO", [])
        if sales_orders:
            prices = [order.get("P") for order in sales_orders]
            prices = [Decimal(price) for price in prices if price]
            return min(prices)
        return None

    async def _get_account_balance(self, assets: Optional[List[str]] = None) -> dict:
        raise NotImplementedError

    async def get_account_balance(self, assets: Optional[List[str]] = None) -> dict:
        res = await self._get_account_balance(assets)
        balance_list = res.get("data", [])
        balance_dict = {
            balance_info["asset"]: balance_info for balance_info in balance_list
        }

        if assets:
            for asset in assets:
                if asset not in balance_dict:
                    balance_dict[asset] = asdict(AssetBalance(asset))

            return {
                asset: balance_info
                for asset, balance_info in balance_dict.items()
                if asset in assets
            }
        else:
            return balance_dict

    async def get_open_orders(self, symbol: str) -> Optional[dict]:
        raise NotImplementedError

    async def get_open_order_balance(self, symbol: str) -> Decimal:
        open_orders = await self.get_open_orders(symbol)

        open_balance = Decimal("0")

        if open_orders:
            data = open_orders.get("data", {})
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            for ask in asks:
                open_balance -= Decimal(ask.get("leftAmount", "0"))
            for bid in bids:
                open_balance += Decimal(bid.get("leftAmount", "0"))

        return open_balance

    async def cancel_order(self, order_id: str) -> Optional[dict]:
        raise NotImplementedError

    async def cancel_open_orders(self, symbol: str, bids=True, asks=True):
        """
        we need order ids

        either read from the saved

        or get open orders
        """
        res = await self.get_open_orders(symbol)
        if not res:
            return

        data = res.get("data", {})
        asks = data.get("asks", [])
        bids = data.get("bids", [])

        results = []
        if bids:
            for order in bids:
                order_id = order.get("id")
                res = await self.cancel_order(order_id)
                results.append(res)

        if asks:
            for order in asks:
                order_id = order.get("id")
                res = await self.cancel_order(order_id)
                results.append(res)

        return results


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
