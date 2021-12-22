import asyncio
from enum import Enum

import simplejson as json  # type: ignore

from blackops.util.logger import logger
from blackops.util.ws import reconnecting_generator, ws_stream


def get_orderbook_message(symbol: str):
    message = [
        151,
        {"type": 151, "channel": "orderbook", "event": symbol, "join": True},
    ]
    return message


def get_obdiff_message(symbol: str):
    message = [
        151,
        {"type": 151, "channel": "obdiff", "event": symbol, "join": True},
    ]
    return message


def get_trade_message(symbol: str):
    message = [
        421,
        {"type": 421, "channel": "trade", "event": symbol, "join": True},
    ]
    return message


MessageType = Enum("MessageType", "ORDERBOOK TRADE OBDIFF")


message_funcs = {
    MessageType.ORDERBOOK: get_orderbook_message,
    MessageType.TRADE: get_trade_message,
    MessageType.OBDIFF: get_obdiff_message,
}


def create_bt_gen(message_type: MessageType, symbol):
    uri = "wss://ws-feed-pro.btcturk.com/"

    message_func = message_funcs[message_type]
    message = message_func(symbol)
    message = json.dumps(message)

    # get sleep from env
    gen = ws_stream(uri, message, sleep=0.11)  # 0.1 sec = 100 ms

    return gen


def create_ws_stream(message_type: MessageType, symbol: str, channel: str = "default"):
    def gen_factory():
        return create_bt_gen(message_type, symbol)

    return reconnecting_generator(gen_factory, channel)


def create_book_stream(symbol: str, channel: str = "default"):
    return create_ws_stream(MessageType.ORDERBOOK, symbol, channel)


async def test_orderbook_stream():
    async for book in create_ws_stream(MessageType.ORDERBOOK, "XRPUSDT"):
        print(book)


async def test_obdiff_stream():
    async for book in create_ws_stream(MessageType.OBDIFF, "USDTTRY"):
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream())
    # asyncio.run(test_obdiff_stream())
