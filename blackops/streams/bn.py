import asyncio

from binance import AsyncClient, BinanceSocketManager  # type:ignore

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


async def binance_stream_generator(
    symbol: str, stream_type: str, channel: str = "default"
):
    try:
        client = await AsyncClient.create()
        bm = BinanceSocketManager(client)
        # ts = bm.kline_socket(symbol, interval)
        # ts = bm.symbol_ticker_socket(symbol)
        ts = bm.multiplex_socket([f"{symbol.lower()}{stream_type}"])

        # then start receiving messages
        async with ts as tscm:
            while True:
                res = await tscm.recv()
                yield res
                await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(e)
        pub.publish_error(channel, str(e))


def create_book_stream_binance(symbol: str, channel: str = "default"):
    return binance_stream_generator(symbol, "@bookTicker", channel)


async def test_orderbook_stream(symbol):
    gen = create_book_stream_binance(symbol)
    async for book in gen:
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream("ANKRUSDT"))
