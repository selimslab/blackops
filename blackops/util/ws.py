import asyncio
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


async def ws_stream(uri: str, message: str, sleep=0.5):
    async with websockets.connect(uri=uri) as websocket:
        while True:
            await websocket.send(message)
            await asyncio.sleep(sleep)
            data = await websocket.recv()
            yield data


async def reconnecting_generator(generator_factory: Callable, channel: str = "default"):
    gen = generator_factory()

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
            # recover from network errors,
            # for example connection lost
            # continue where you left

            # create a new generator
            gen = generator_factory()

            logger.error(f"Reconnecting btc stream: {e}")
            pub.publish_error(channel, str(e))

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            logger.error(f"BT stream lost: {e}")

            pub.publish_error(channel, str(e))
            raise e
