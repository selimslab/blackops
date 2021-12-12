import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv

load_dotenv()


def get_headers() -> dict:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY", "")

    apiSecret = base64.b64decode(apiSecret)  # type: ignore

    stamp = str(int(time.time()) * 1000)

    data = "{}{}".format(apiKey, stamp).encode("utf-8")

    signature = hmac.new(apiSecret, data, hashlib.sha256).digest()  # type: ignore
    signature = base64.b64encode(signature)

    headers = {
        "X-PCK": apiKey,
        "X-Stamp": stamp,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }

    return headers


api_base = "https://api.btcturk.com"
ticker_pair = "USDT_TRY"


def get_data(url: str):
    with requests.get(url, stream=True, headers=get_headers()) as r:
        if r.status_code == 200:
            print(r.json())
        else:
            print(str(r.status_code), r.reason)


def get_ticker():
    ticker_path = "/api/v2/ticker"
    ticker_url = urllib.parse.urljoin(api_base, ticker_path)
    ticker_url = f"{ticker_url}?pairSymbol={ticker_pair}"
    get_data(ticker_url)


def get_orderbook():
    orderbook_path = "api/v2/orderbook"
    orderbook_url = urllib.parse.urljoin(api_base, orderbook_path)
    orderbook_url = f"{orderbook_url}?pairSymbol={ticker_pair}"
    get_data(orderbook_url)


def get_balance():
    path = "api/v1/users/balances"
    url = urllib.parse.urljoin(api_base, path)
    get_data(url)


def submit_order(qty, price, order_type):
    headers = get_headers()

    path = "/api/v1/order"
    url = urllib.parse.urljoin(api_base, path)
    params = {
        "quantity": 0.001,
        "price": 50000,
        "stopPrice": 0,
        "newOrderClientId": "BtcTurk Python API Test",
        "orderMethod": "limit",
        "orderType": "sell",
        "pairSymbol": "BTC_TRY",
    }
    result = requests.post(url=url, headers=headers, json=params)
    result = result.json()
    print(json.dumps(result, indent=2))


def buy(qty, price):
    submit_order(qty, price, "buy")


if __name__ == "__main__":
    get_balance()
