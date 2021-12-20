import base64
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, List, Optional

import aiohttp

from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.btcturk.base import BtcturkBase
from blackops.util.logger import logger
from blackops.util.url import update_url_query_params


@dataclass
class BtcturkApiClient(BtcturkBase):

    api_key: str = "no key"
    api_secret: str = "no secret"

    api_base = "https://api.btcturk.com"
    order_url = urllib.parse.urljoin(api_base, "/api/v1/order")
    balance_url = urllib.parse.urljoin(api_base, "/api/v1/users/balances")
    all_orders_url = urllib.parse.urljoin(api_base, "/api/v1/allOrders")
    open_orders_url = urllib.parse.urljoin(api_base, "/api/v1/openOrders")

    name: str = "btcturk_real"

    def __post_init__(self):
        self.headers = self._get_headers()
        self.session = aiohttp.ClientSession()

    def _get_headers(self) -> dict:
        decoded_api_secret = base64.b64decode(self.api_secret)  # type: ignore

        stamp = str(int(time.time()) * 1000)

        data = "{}{}".format(self.api_key, stamp).encode("utf-8")

        signature = hmac.new(decoded_api_secret, data, hashlib.sha256).digest()  # type: ignore
        signature = base64.b64encode(signature)

        headers = {
            "X-PCK": self.api_key,
            "X-Stamp": stamp,
            "X-Signature": signature.decode(),  # turn bytes into str because aiothhp headers expects str
            "Content-Type": "application/json",
        }

        return headers

    async def _http(self, uri: str, method: Callable):
        async with method(uri, headers=self._get_headers()) as res:
            if res.status == 200:
                return await res.json()
            else:
                msg = f"{str(res.status)} {res.reason} {uri}"
                logger.error(msg)
                return {}

    async def get_account_balance(self, assets: Optional[List[str]] = None) -> dict:
        res = await self._http(self.balance_url, self.session.get)

        balance_list = res.get("data", [])
        if not assets:
            return {
                balance_info["asset"]: balance_info for balance_info in balance_list
            }

        return {
            balance_info["asset"]: balance_info
            for balance_info in balance_list
            if balance_info["asset"] in assets
        }

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> Optional[dict]:

        params = {
            "quantity": quantity,
            "price": price,
            "stopPrice": price,
            "orderMethod": "limit",
            "orderType": order_type,
            "pairSymbol": pair.symbol,
        }

        async with self.session.post(
            self.order_url, headers=self._get_headers(), json=params
        ) as res:
            return await res.json(content_type=None)

    async def get_all_orders(self, params: dict) -> Optional[dict]:
        uri = update_url_query_params(self.all_orders_url, params)
        return await self._http(uri, self.session.get)

    async def get_open_orders(self, symbol: str) -> Optional[dict]:
        if not symbol:
            raise Exception("symbol is required")

        params = {"pairSymbol": symbol}
        uri = update_url_query_params(self.open_orders_url, params)
        return await self._http(uri, self.session.get)

    async def get_open_order_balance(self, symbol: str) -> Decimal:
        open_orders = await self.get_open_orders(symbol)

        open_balance = Decimal("0")

        if open_orders:
            data = open_orders.get("data", {})
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            for ask in asks:
                open_balance += Decimal(ask.get("leftAmount", "0"))
            for bid in bids:
                open_balance -= Decimal(bid.get("leftAmount", "0"))

        return open_balance

    async def cancel_order(self, order_id: str) -> Optional[dict]:
        if not order_id:
            raise Exception("order id is required")

        uri = update_url_query_params(self.order_url, {"id": order_id})
        return await self._http(uri, self.session.delete)

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

    async def _close_session(self):
        await self.session.close()


# def get_ticker(pair:str):
#     ticker_path = "/api/v2/ticker"
#     ticker_url = urllib.parse.urljoin(api_base, ticker_path)
#     ticker_url = f"{ticker_url}?pairSymbol={pair}"
#     get_data(ticker_url)


# def get_orderbook(pair:str):
#     orderbook_path = "api/v2/orderbook"
#     orderbook_url = urllib.parse.urljoin(api_base, orderbook_path)
#     orderbook_url = f"{orderbook_url}?pairSymbol={pair}"
#     get_data(orderbook_url)


# @dataclass
# class Order:
#     id: str
#     quantity: str
#     price: str
#     stopPrice: str
#     method: str
#     type :str
#     datetime: str
#     newOrderClientId: str
#     pairSymbol: str
#     pairSymbolNormalized: str
