import asyncio
from enum import Enum
from typing import AsyncGenerator

import simplejson as json  # type: ignore

from src.monitoring import logger
from src.web.ws import reconnecting_generator, ws_stream


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


def get_ticker_message(symbol: str):
    message = [
        402,
        {"type": 402, "channel": "ticker", "event": symbol, "join": True},
    ]
    return message


MessageType = Enum("MessageType", "ORDERBOOK TRADE OBDIFF TICKER")


message_funcs = {
    MessageType.ORDERBOOK: get_orderbook_message,
    MessageType.TRADE: get_trade_message,
    MessageType.OBDIFF: get_obdiff_message,
    MessageType.TICKER: get_ticker_message,  # ticker not working
}


def create_bt_gen(message_type: MessageType, symbol, sleep_seconds):
    uri = "wss://ws-feed-pro.btcturk.com/"

    message_func = message_funcs[message_type]
    message = message_func(symbol)
    message = json.dumps(message)

    # get sleep from env
    gen = ws_stream(uri, message, sleep=sleep_seconds)  # 0.1 sec = 100 ms

    return gen


def create_reconnecting_ws_stream(
    message_type: MessageType, symbol: str, channel: str, sleep_seconds: float
):
    def gen_factory():
        return create_bt_gen(message_type, symbol, sleep_seconds)

    return reconnecting_generator(gen_factory, channel)


async def parsing_generator(gen: AsyncGenerator):
    async for data in gen:
        if data:
            try:
                yield json.loads(data)[1]
            except Exception as e:
                logger.error(f"parsing_gen: {e}")
                continue


def create_book_stream(
    symbol: str, channel: str = "default", sleep_seconds: float = 0.11
) -> AsyncGenerator:
    gen = create_reconnecting_ws_stream(
        MessageType.ORDERBOOK, symbol, channel, sleep_seconds
    )
    return parsing_generator(gen)


async def test_parsing_gen(symbol: str):
    async for book in create_book_stream(symbol):
        print(book)


if __name__ == "__main__":
    # asyncio.run(test_stream(MessageType.ORDERBOOK, "USDTTRY"))
    # asyncio.run(test_obdiff_stream())
    asyncio.run(test_parsing_gen("ETHUSDT"))
