import asyncio
from typing import Callable, Optional

import async_timeout
from aiohttp.client_exceptions import ClientConnectionError
from binance import AsyncClient, BinanceSocketManager, Client  # type:ignore

import src.pubsub.log_pub as log_pub
from src.monitoring import logger


class BinanceWebSocketException(Exception):
    pass


class BinanceOverflowException(Exception):
    pass


class ClientFactory:
    client: Optional[AsyncClient] = None
    socket_manager: Optional[BinanceSocketManager] = None

    async def get_client(self):
        if not self.client:
            self.client = await AsyncClient.create()
        return self.client

    async def get_socket_manager(self):
        client = await self.get_client()
        if not self.socket_manager:
            self.socket_manager = BinanceSocketManager(client)
        return self.socket_manager

    async def close_connection(self):
        await self.client.close_connection()


client_factory = ClientFactory()


async def binance_stream_generator(symbol: str, stream_type: str):
    try:
        bm = await client_factory.get_socket_manager()
        ts = bm.multiplex_socket([f"{symbol.lower()}{stream_type}"])

        async with ts as tscm:
            while True:
                msg = await tscm.recv()

                if msg and msg.get("e", "") == "error":
                    raise BinanceWebSocketException(msg)

                if msg:
                    yield msg

                await asyncio.sleep(0)

    except Exception as e:
        client_factory.close_connection()
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


def create_book_stream(symbol: str):
    def create_new_socket_conn():
        return binance_stream_generator(symbol, "@bookTicker")

    return reconnecting_binance_generator(create_new_socket_conn)


async def test_orderbook_stream(symbol):
    gen = create_book_stream(symbol)
    seen = 0
    async with async_timeout.timeout(10):
        async for book in gen:
            print(seen, book)
            seen += 1


async def main():
    client = await AsyncClient.create()

    res = await client.get_exchange_info()
    print(client.response.headers)

    await client.close_connection()


async def candle_gen(symbol: str):
    client = await client_factory.get_client()

    candles = await client.get_klines(
        symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=1
    )

    print(candles)


if __name__ == "__main__":
    # asyncio.run(test_orderbook_stream("ADAUSDT"))
    # asyncio.run(main())
    asyncio.run(candle_gen("ADAUSDT"))
