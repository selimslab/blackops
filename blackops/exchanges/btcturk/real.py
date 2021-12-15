import base64
import hashlib
import hmac
import itertools
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

import aiohttp
import requests

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

    orders: list = []

    def __post_init__(self):
        self.headers = self.get_headers()
        self.session = aiohttp.ClientSession()

    def get_headers(self) -> dict:
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

    async def get_data(self, url: str) -> dict:
        try:
            with requests.get(url, stream=True, headers=self.headers) as r:
                if r.status_code == 200:
                    print(r.json())
                    return r.json()
                else:
                    print(str(r.status_code), r.reason)
                    return {}
        except Exception as e:
            logger.error(e)
            return {}

    async def get_account_balance(self, assets: List[str]):
        res = await self.get_data(self.balance_url)

        balance_list = res.get("data", [])
        if not assets:
            return balance_list

        return [bl for bl in balance_list if bl["asset"] in assets]

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):

        params = {
            "quantity": quantity,
            "price": price,
            "stopPrice": price,
            # "newOrderClientId": "ops",
            "orderMethod": "limit",
            "orderType": order_type,
            "pairSymbol": pair_symbol,
        }

        async with self.session.post(
            self.order_url, headers=self.headers, json=params
        ) as res:
            return res

            # self.orders.append(result)

            # data = result.get("data", {})
            # order_id = data.get("id")
            # timestamp = data.get("timestamp")

            # print(json.dumps(result, indent=2))

    async def get_all_orders(self, params: dict) -> Optional[dict]:
        uri = update_url_query_params(self.all_orders_url, params)
        async with self.session.get(uri, headers=self.headers) as res:
            return await res.json()

    async def get_open_orders(self, symbol: str) -> Optional[dict]:
        if not symbol:
            raise Exception("symbol is required")

        uri = update_url_query_params(self.open_orders_url, {"pairSymbol": symbol})
        async with self.session.get(uri, headers=self.headers) as res:
            return await res.json()

    async def cancel_order(self, order_id: str) -> Optional[dict]:
        if not order_id:
            raise Exception("order id is required")

        uri = update_url_query_params(self.order_url, {"id": order_id})
        async with self.session.delete(uri, headers=self.headers) as res:
            return await res.json()

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

        if bids:
            for order in bids:
                order_id = order.get("id")
                await self.cancel_order(order_id)
        if asks:
            for order in asks:
                order_id = order.get("id")
                await self.cancel_order(order_id)

    def get_saved_orders(self):
        return self.orders

    async def close_session(self):
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
