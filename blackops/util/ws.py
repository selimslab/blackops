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
    # async with websockets.connect(uri=uri) as ws:
    ws = await websockets.connect(uri=uri)

    # async for ws in websockets.connect(uri=uri):
    #     try:
    #         while True:
    #             pong_waiter = await ws.ping()
    #             await pong_waiter
    #             await ws.send(message)
    #             data = await ws.recv()
    #             yield data
    #     except websockets.exceptions.ConnectionClosed:
    #         continue

    while True:

        if not ws.open:
            ws = await websockets.connect(uri=uri)
            logger.info("Reconnecting to btcturk")

        await ws.send(message)
        data = await ws.recv()
        yield data
        await asyncio.sleep(sleep)


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
