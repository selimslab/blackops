import asyncio
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


async def ws_stream(uri: str, message: str, sleep=0.1):
    async with websockets.connect(uri=uri) as websocket:
        while True:
            await websocket.send(message)
            await asyncio.sleep(sleep)
            data = await websocket.recv()
            yield data


async def reconnecting_generator(generator_factory: Callable, channel: str = "default"):
    gen = generator_factory()

    retries = 0
    max_retry = 400

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
            # if retries > max_retry:
            #     msg = (
            #         f"Stopping, btcturk stream is too unstable (retries {retries}): {e}"
            #     )
            #     log_and_publish_error(channel, msg)
            #     raise e
            # create a new generator

            retries += 1
            gen = generator_factory()
            msg = f"Reconnecting btc ({retries}): {e}"
            logger.error(msg)
            # pub.publish_message(channel, msg)
        except Exception as e:
            # log and raise any other error
            # for example a KeyError

            msg = f"BT stream lost: {e}"
            logger.error(msg)
            pub.publish_error(channel, msg)
            raise e
