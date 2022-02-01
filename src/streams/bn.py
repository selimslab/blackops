import asyncio
from typing import Callable

import async_timeout
from aiohttp.client_exceptions import ClientConnectionError
from binance import AsyncClient, BinanceSocketManager  # type:ignore

import src.pubsub.log_pub as log_pub
from src.monitoring import logger


class BinanceWebSocketException(Exception):
    pass


class BinanceOverflowException(Exception):
    pass


class BinanceFactory:
    client: AsyncClient = None
    sm: BinanceSocketManager = None

    async def get_client(self):
        if not self.client:
            self.client = await AsyncClient.create()

        return self.client

    async def get_socket_manager(self):
        client = await self.get_client()
        if not self.sm:
            self.sm = BinanceSocketManager(client)
        return self.sm


bn_factory = BinanceFactory()


async def binance_stream_generator(symbol: str, stream_type: str):
    try:
        sm = await bn_factory.get_socket_manager()
        ts = sm.multiplex_socket([f"{symbol.lower()}@{stream_type}"])

        async with ts as tscm:
            while True:
                msg = await tscm.recv()

                if msg and msg.get("e", "") == "error":
                    raise BinanceWebSocketException(msg)

                if msg:
                    yield msg

                await asyncio.sleep(0)

    except Exception as e:
        # await client.close_connection()
        msg = f"binance stream disconnected: {e}"
        logger.error(f"binance_stream_generator: {msg}")
        raise e


async def reconnecting_binance_generator(generator_factory: Callable):

    retries = 0

    gen = generator_factory()

    while True:
        try:
            async for data in gen:
                if data:
                    yield data
                await asyncio.sleep(0)
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
            asyncio.TimeoutError,
        ) as e:
            # recover from network errors,
            # for example connection lost
            # continue where you left
            retries += 1

            # create a new generator
            gen = generator_factory()

            msg = f"Reconnecting binance ({retries}), {e}"
            logger.info(f"reconnecting_binance_generator: {msg}")
            continue

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            msg = f"Binance stream lost: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            raise e


def create_stream(symbol: str, stream_type: str):
    def create_new_socket_conn():
        return binance_stream_generator(symbol, stream_type)

    return reconnecting_binance_generator(create_new_socket_conn)


def create_book_stream(symbol: str):
    return create_stream(symbol, "bookTicker")


def create_kline_stream(symbol: str):
    return create_stream(symbol, "kline_1m")


async def get_klines(symbol: str, interval: str, limit=7):
    client = await bn_factory.get_client()

    res = await client.get_klines(symbol=symbol, interval=interval, limit=limit)
    return res


proc = 0


async def work():
    global proc
    await asyncio.sleep(0.01)
    proc += 1
    print("proc", proc)


async def test_stream(symbol):
    gen = create_kline_stream(symbol)
    seen = 0
    async with async_timeout.timeout(10):
        async for book in gen:
            seen += 1
            print(book)
            await work()


async def main():
    print(await get_klines("MANAUSDT", "1m"))


if __name__ == "__main__":
    # asyncio.run(test_stream("MANAUSDT"))
    asyncio.run(main())
