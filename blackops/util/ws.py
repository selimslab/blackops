import asyncio
from typing import Callable

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    WebSocketException,
)

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


async def ws_stream(uri: str, message: str, sleep=0):
    async with websockets.connect(uri=uri) as ws:  # type: ignore
        while True:
            await ws.send(message)
            data = await ws.recv()
            yield data
            await asyncio.sleep(sleep)


async def reconnecting_generator(generator_factory: Callable, channel: str = "default"):
    gen = generator_factory()

    retries = 0
    # max_retry = 400

    while True:
        try:
            async for data in gen:
                if data:
                    yield data
        except (
            ConnectionClosedError,
            ConnectionAbortedError,
            ConnectionResetError,
            WebSocketException,
        ) as e:
            retries += 1
            gen = generator_factory()
            msg = f"Reconnecting, retries: {retries}: {e}"
            logger.error(f"reconnecting_generator: {msg}")
        except Exception as e:
            msg = f"WS stream lost: {e}"
            logger.error(f"reconnecting_generator: {msg}")
            pub.publish_error(channel, msg)
            raise e
