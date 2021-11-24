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


async def binance_stream_generator(
    symbol: str, stream_type: str, channel: str = "default", sleep=0.1
):
    try:
        client = await AsyncClient.create()
        bm = BinanceSocketManager(client, user_timeout=1)
        # ts = bm.kline_socket(symbol, interval)
        # ts = bm.symbol_ticker_socket(symbol)
        ts = bm.multiplex_socket([f"{symbol.lower()}{stream_type}"])

        # then start receiving messages
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
                        if "overflow" in msg.get("m", "").lower():
                            raise BinanceOverflowException(msg)
                        else:
                            raise BinanceWebSocketException(msg)

                    yield msg

                await asyncio.sleep(sleep)

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

    retries = 0
    max_retry = 500
    sleep = 0.18

    gen = generator_factory(sleep)

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

            if isinstance(e, BinanceOverflowException):
                sleep += 0.02  # add 10ms to sleep
                if sleep > 0.3:  # it stays behind btc
                    msg = "sleep increased too much, staying behind follower exchanges"
                    logger.error(msg)
                    sleep = 0.2

            if retries > max_retry:
                msg = f"Binance stream lost: {e}"
                log_and_publish_error(channel, msg)
                raise e

            # create a new generator
            gen = generator_factory(sleep)

            retries += 1
            msg = f"Reconnecting binance stream (retry step {retries}) (sleep {sleep} seconds): {e}"
            log_and_publish_error(channel, msg)
            continue

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            msg = f"Binance stream lost: {e}"
            log_and_publish_error(channel, msg)

            raise e


def create_book_stream_binance(symbol: str, channel: str = "default"):
    def create_new_socket_conn(sleep):
        return binance_stream_generator(symbol, "@bookTicker", channel, sleep)

    return reconnecting_binance_generator(create_new_socket_conn, channel)


async def test_orderbook_stream(symbol):
    gen = create_book_stream_binance(symbol)
    async for book in gen:
        print(book)


if __name__ == "__main__":
    asyncio.run(test_orderbook_stream("ANKRUSDT"))
