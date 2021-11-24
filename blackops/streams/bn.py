import asyncio
from typing import Callable

from aiohttp.client_exceptions import ClientConnectionError
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
        msg = f"binance stream disconnected: {e}"
        logger.error(msg)
        raise e


def log_and_publish_error(channel, msg):
    logger.error(msg)
    pub.publish_error(channel, msg)


async def reconnecting_binance_generator(
    generator_factory: Callable, channel: str = "default"
):
    gen = generator_factory()

    retries = 0
    max_retry = 10

    while True:
        try:
            async for data in gen:
                if data:
                    yield data
        except (
            ConnectionAbortedError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionError,
            ClientConnectionError,
            TimeoutError,
        ) as e:
            # recover from network errors,
            # for example connection lost
            # continue where you left
            if retries > max_retry:
                msg = f"Binance stream lost: {e}"
                log_and_publish_error(channel, msg)
                raise e
            # create a new generator
            gen = generator_factory()

            retries += 1
            msg = f"Reconnecting binance stream (retry step {retries}): {e}"
            log_and_publish_error(channel, msg)
            continue

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            msg = f"Binance stream lost: {e}"
            log_and_publish_error(channel, msg)

            raise e


def create_book_stream_binance(symbol: str, channel: str = "default"):
    def create_new_socket_conn():
        return binance_stream_generator(symbol, "@bookTicker", channel)

    return reconnecting_binance_generator(create_new_socket_conn, channel)


async def test_orderbook_stream(symbol):
    gen = create_book_stream_binance(symbol)
    async for book in gen:
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream("ANKRUSDT"))
