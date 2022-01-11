import asyncio
from dataclasses import dataclass
from typing import Callable

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    WebSocketException,
)

import src.pubsub.log_pub as log_pub
from src.monitoring import logger


async def ws_stream(uri: str, message: str, sleep=0):
    async with websockets.connect(uri=uri) as ws:  # type: ignore
        while True:
            await ws.send(message)
            data = await ws.recv()
            yield data
            await asyncio.sleep(sleep)


@dataclass
class ResilientGenerator:
    retries = 0

    async def reconnecting_generator(self, generator_factory: Callable):
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
                self.retries += 1
                gen = generator_factory()
            except Exception as e:
                msg = f"WS stream lost: {e}"
                logger.error(f"reconnecting_generator: {msg}")
                raise e
