import asyncio
import json

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

    gen = ws_stream(uri, message, sleep=0.2)

    return gen


def create_book_stream_btcturk(symbol: str, channel: str = "default"):
    def gen_factory():
        return create_orderbook_gen(symbol)

    return reconnecting_generator(gen_factory, channel)


async def test_orderbook_stream():
    async for book in create_book_stream_btcturk("USDTTRY"):
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream())
