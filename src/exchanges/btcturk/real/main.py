import asyncio
import base64
import hashlib
import hmac
import time
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

import aiohttp

from src.stgs import Asset, AssetPair
from src.exchanges.btcturk.base import BtcturkBase
from src.monitoring import logger
from src.web.url import update_url_query_params


@dataclass
class BtcturkApiClient(BtcturkBase):

    api_key: str = "no key"
    api_secret: str = "no secret"

    api_base = "https://api.btcturk.com"
    order_url = urllib.parse.urljoin(api_base, "/api/v1/order")
    balance_url = urllib.parse.urljoin(api_base, "/api/v1/users/balances")
    all_orders_url = urllib.parse.urljoin(api_base, "/api/v1/allOrders")
    open_orders_url = urllib.parse.urljoin(api_base, "/api/v1/openOrders")
    ticker_url = urllib.parse.urljoin(api_base, "/api/v2/ticker")

    name: str = "btcturk_real"

    rate_limit_lock = asyncio.Lock()
    rate_limit_seconds: int = 4

    order_lock = asyncio.Lock()

    def __post_init__(self):
        self.headers = self._get_headers()
        self.session = aiohttp.ClientSession()

    @asynccontextmanager
    async def timed_order_context(self):
        print("timed_order_context")
        async with self.order_lock:
            yield 
            await asyncio.sleep(0.1)

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

    async def activate_rate_limit(self) -> None:
        with self.rate_limit_lock:
            await self._close_session()
            self.session = aiohttp.ClientSession()
            await asyncio.sleep(self.rate_limit_seconds)

    async def _get(self, uri: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(uri) as res:
                    return await res.json()
        except Exception as e:
            logger.error(f"_get {e}")

    async def _http(self, uri: str, method: Callable):
        try:
            if self.rate_limit_lock.locked():
                return
            async with method(uri, headers=self._get_headers()) as res:
                if res.status == 200:
                    return await res.json()
                if res.status == 429:
                    await self.activate_rate_limit()
                    msg = f"""got 429 too many requests, 
                    will wait {self.rate_limit_seconds} seconds before sending new requests"""
                    raise Exception(msg)
                else:
                    msg = f"_http: {str(res.status)} {res.reason} {uri}"
                    raise Exception(msg)
        except Exception as e:
            msg = f"http: {method} {uri} {e}"
            raise Exception(msg)

    async def get_account_balance(self) -> Optional[dict]:
        """
        {'asset': 'USDT',
         'assetname': 'Tether',
         'balance': '3104.207625000000019',
         'free': '3104.207625000000019',
         'locked': '0',
         'orderFund': '0',
         'precision': 2,
         'requestFund': '0'},
        """
        try:
            return await self._http(self.balance_url, self.session.get)
        except Exception as e:
            raise e

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> Optional[dict]:
        """
        {'code': 0,
                'data': {'datetime': 1640119334586,
                        'id': 6067193862,
                        'method': 'limit',
                        'newOrderClientId': '3a9d2346-a070-44cd-b37c-fad9b9f4bd88',
                        'pairSymbol': 'XRPUSDT',
                        'pairSymbolNormalized': 'XRP_USDT',
                        'price': '1.0000',
                        'quantity': '10',
                        'stopPrice': '1',
                        'type': 'sell'},
        'httpStatusCode': 200,
        'message': 'SUCCESS',
        'success': True}
        """
        params = {
            "quantity": quantity,
            "price": price,
            "stopPrice": price,
            "orderMethod": "limit",
            "orderType": order_type,
            "pairSymbol": pair.symbol,
        }
        try:
            if self.order_lock.locked():
                logger.info("another order in progress")
                return None
            async with self.timed_order_context():
                async with self.session.post(
                    self.order_url, headers=self._get_headers(), json=params
                ) as res:
                    return await res.json(content_type=None)
        except Exception as e:
            logger.error(f"submit_limit_order: {e}")
            raise e

    async def get_open_orders(self, pair: AssetPair) -> Optional[dict]:

        """
        {'code': 0,
         'data': {'asks': [{'amount': '15.0000',
                            'id': 6058774319,
                            'leftAmount': '15.0000',
                            'method': 'limit',
                            'orderClientId': '005f56a6-bc0c-4f6a-924b-f732689024d7',
                            'pairSymbol': 'XRPUSDT',
                            'pairSymbolNormalized': 'XRP_USDT',
                            'price': '1.0000',
                            'quantity': '15.0000',
                            'status': 'Untouched',
                            'stopPrice': '1.0000',
                            'time': 0,
                            'type': 'sell',
                            'updateTime': 1640076570793},
                           {'amount': '10.0000',
                            'id': 6067193862,
                            'leftAmount': '10.0000',
                            'method': 'limit',
                            'orderClientId': '3a9d2346-a070-44cd-b37c-fad9b9f4bd88',
                            'pairSymbol': 'XRPUSDT',
                            'pairSymbolNormalized': 'XRP_USDT',
                            'price': '1.0000',
                            'quantity': '10.0000',
                            'status': 'Untouched',
                            'stopPrice': '1.0000',
                            'time': 0,
                            'type': 'sell',
                            'updateTime': 1640119334587}],
                  'bids': []},
         'message': None,
         'success': True}

        """
        if not pair:
            raise Exception("pair is required")

        params = {"pairSymbol": pair.symbol}
        uri = update_url_query_params(self.open_orders_url, params)
        return await self._http(uri, self.session.get)

    async def cancel_order(self, order_id: int) -> Optional[dict]:
        try:
            if not order_id:
                return None
            uri = update_url_query_params(self.order_url, {"id": order_id})
            return await self._http(uri, self.session.delete)
        except Exception as e:
            # we could not cancel the order, its normal
            logger.info(f"cancel_order: {e}")
            return None

    # async def get_all_orders(self, params: dict) -> Optional[dict]:
    #     uri = update_url_query_params(self.all_orders_url, params)
    #     return await self._http(uri, self.session.get)

    async def get_ticker(self, pair: AssetPair) -> Optional[Decimal]:
        params = {"pairSymbol": pair.symbol}
        uri = update_url_query_params(self.ticker_url, params)
        res = await self._get(uri)
        if not res:
            return None
        try:
            data = res["data"][0]
            bid, ask = data["bid"], data["ask"]
            return (Decimal(str(bid)) + Decimal(str(ask))) / Decimal("2")
        except Exception as e:
            logger.error(f"get_ticker {e}")
            return None

    # def get_orderbook(pair:str):
    #     orderbook_path = "api/v2/orderbook"
    #     orderbook_url = urllib.parse.urljoin(api_base, orderbook_path)
    #     orderbook_url = f"{orderbook_url}?pairSymbol={pair}"
    #     get_data(orderbook_url)

    async def _close_session(self):
        await self.session.close()
