import base64
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

import aiohttp

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair
from src.domain.models import OrderType
from src.environment import sleep_seconds
from src.exchanges.btcturk.base import BtcturkBase
from src.monitoring import logger
from src.periodic import StopwatchContext, lock_with_timeout
from src.web import update_url_query_params


@dataclass(frozen=True)
class URLs:
    api_base = "https://api.btcturk.com"
    order_url = urllib.parse.urljoin(api_base, "/api/v1/order")
    balance_url = urllib.parse.urljoin(api_base, "/api/v1/users/balances")
    all_orders_url = urllib.parse.urljoin(api_base, "/api/v1/allOrders")
    open_orders_url = urllib.parse.urljoin(api_base, "/api/v1/openOrders")
    ticker_url = urllib.parse.urljoin(api_base, "/api/v2/ticker")


@dataclass
class BtcturkApiClient(BtcturkBase):

    api_key: str = "no key"
    api_secret: str = "no secret"

    urls: URLs = URLs()

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
        try:
            if self.locks.rate_limit.locked():
                return
            async with method(uri, headers=self._get_headers()) as res:
                if res.status == 200:
                    return await res.json(content_type=None)
                elif res.status == 429:
                    await self.activate_rate_limit()
                    msg = f"""got 429 too many requests, 
                    will wait {sleep_seconds.rate_limit} seconds before sending new requests"""
                    raise Exception(msg)
                elif res.status == 400:
                    msg = f"got 400 bad request, {uri}"
                    # logger.info(msg)
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
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()

            return await self._http(self.urls.balance_url, self.session.get)
        except Exception as e:
            raise e

    async def submit_limit_order(
        self, pair: AssetPair, side: OrderType, price: float, quantity: float
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

        try:
            if side == OrderType.BUY:
                lock = self.locks.buy
                wait = sleep_seconds.buy_wait
            else:
                lock = self.locks.sell
                wait = sleep_seconds.sell_wait

            if lock.locked():
                return None

            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()

            async with lock_with_timeout(lock, wait) as ok:
                if ok:
                    params = {
                        "quantity": quantity,
                        "price": price,
                        # "stopPrice": price,
                        "orderMethod": "limit",
                        "orderType": side.value,
                        "pairSymbol": pair.symbol,
                    }
                    async with self.session.post(
                        self.urls.order_url, headers=self._get_headers(), json=params
                    ) as res:
                        return await res.json(content_type=None)

            return None

        except Exception as e:
            msg = f"submit_limit_order: {e}"
            logger.error(msg)
            log_pub.publish_error(msg)
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
        uri = update_url_query_params(self.urls.open_orders_url, params)

        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        async with lock_with_timeout(self.locks.read, sleep_seconds.read_wait) as ok:
            if ok:
                return await self._http(uri, self.session.get)

        return None

    async def cancel_order(self, order_id: int) -> Optional[dict]:
        try:
            if not order_id:
                return None
            if self.locks.cancel.locked():
                return None

            uri = update_url_query_params(self.urls.order_url, {"id": order_id})

            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()

            async with lock_with_timeout(
                self.locks.cancel, sleep_seconds.cancel_wait
            ) as ok:
                if ok:
                    return await self._http(uri, self.session.delete)

            return None
        except Exception as e:
            # we could not cancel the order, its normal
            logger.info(f"cancel_order: {e}")
            return None

    # async def get_all_orders(self, params: dict) -> Optional[dict]:
    #     uri = update_url_query_params(self.all_orders_url, params)
    #     return await self._http(uri, self.session.get)

    async def _get(self, uri: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(uri) as res:
                    return await res.json(content_type=None)
        except Exception as e:
            logger.error(f"_get {e}")

    async def get_ticker(self, pair: AssetPair) -> Optional[Decimal]:
        params = {"pairSymbol": pair.symbol}
        uri = update_url_query_params(self.urls.ticker_url, params)
        res = await self._get(uri)
        if not res:
            return None
        try:
            data = res["data"][0]
            bid, ask = data["bid"], data["ask"]
            return (Decimal(str(bid)) + Decimal(str(ask))) / Decimal("2")
        except Exception as e:
            msg = f"get_ticker {e}"
            logger.error(msg)
            log_pub.publish_error(msg)
            return None
