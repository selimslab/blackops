import asyncio
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException

from blackops.util.logger import logger


async def ws_stream(uri: str, message: str, sleep=0.5):
    async with websockets.connect(uri=uri) as websocket:
        while True:
            await websocket.send(message)
            await asyncio.sleep(sleep)
            data = await websocket.recv()
            yield data


async def reconnecting_generator(generator_factory: Callable):
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

            logger.info(f"Reconnecting generator: {e}")

            # pusher_client.trigger(self.sha, event.update, message)
            # TODO sha needed here

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            raise e
