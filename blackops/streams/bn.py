import asyncio
from typing import Callable

from aiohttp.client_exceptions import ClientConnectionError
from binance import AsyncClient, BinanceSocketManager  # type:ignore

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


class BinanceWebSocketException(Exception):
    pass


class BinanceOverflowException(Exception):
    pass


async def binance_stream_generator(symbol: str, stream_type: str):
    client = await AsyncClient.create()
    try:
        # TODO multiple streams from the same ws
        # f"ethusdt{stream_type}"
        bm = BinanceSocketManager(client)
        ts = bm.multiplex_socket([f"{symbol.lower()}{stream_type}"])

        async with ts as tscm:
            while True:
                msg = await tscm.recv()
                if msg:
                    """
                    {
                        'e': 'error',
                        'm': 'Max reconnect retries reached'
                    }
                    """
                    if msg.get("e", "") == "error":
                        raise BinanceWebSocketException(msg)

                    yield msg

                await asyncio.sleep(0)

    except Exception as e:
        await client.close_connection()
        msg = f"binance stream disconnected: {e}"
        logger.error(msg)
        raise e


def log_and_publish_error(channel, msg):
    logger.error(msg)
    pub.publish_error(channel, msg)


def log_and_publish_message(channel, msg):
    logger.error(msg)
    pub.publish_message(channel, msg)


async def reconnecting_binance_generator(
    generator_factory: Callable, channel: str = "default"
):

    retries = 0

    gen = generator_factory()

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
            BinanceWebSocketException,
            BinanceOverflowException,
        ) as e:
            # recover from network errors,
            # for example connection lost
            # continue where you left
            retries += 1

            # create a new generator
            gen = generator_factory()

            msg = f"Reconnecting binance ({retries}), {e}"
            logger.info(msg)
            continue

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            msg = f"Binance stream lost: {e}"
            log_and_publish_error(channel, msg)

            raise e


def create_book_stream(symbol: str, channel: str = "default"):
    def create_new_socket_conn():
        return binance_stream_generator(symbol, "@bookTicker")

    return reconnecting_binance_generator(create_new_socket_conn, channel)


async def test_orderbook_stream(symbol):
    gen = create_book_stream(symbol)
    async for book in gen:
        print(book)


async def main():
    client = await AsyncClient.create()

    res = await client.get_exchange_info()
    print(client.response.headers)

    await client.close_connection()


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream("MANAUSDT"))
    # asyncio.run(main())
