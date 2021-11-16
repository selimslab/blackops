import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException

from blackops.util.logger import logger
from blackops.util.ws import reconnecting_generator, ws_stream


def get_orderbook_message(symbol: str):
    # obdiff
    message = [
        151,
        {"type": 151, "channel": "orderbook", "event": symbol, "join": True},
    ]
    return message


def create_orderbook_gen(symbol: str):
    uri = "wss://ws-feed-pro.btcturk.com/"

    message = get_orderbook_message(symbol)
    message = json.dumps(message)

    gen = ws_stream(uri, message)

    return gen


def create_book_stream(symbol: str):
    gen_factory = lambda: create_orderbook_gen(symbol)
    return reconnecting_generator(gen_factory)


async def test_orderbook_stream():
    async for book in create_book_stream("USDTTRY"):
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream())
