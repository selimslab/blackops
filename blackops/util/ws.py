from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException


async def ws_stream(uri:str, message:str):
    async with websockets.connect(uri=uri) as websocket:
        while True:
            await websocket.send(message)
            data = await websocket.recv()
            yield data


async def reconnecting_generator(generator_factory:Callable):
    gen = generator_factory()

    while True:
        try:
            async for data in gen:
                if data:
                    yield data
        except ConnectionClosedError as e:
            # recover from network errors, 
            # for example connection lost
            # continue where you left

            # create a new generator
            gen = generator_factory()

        except Exception as e:
            # log and raise any other error
            # for example a KeyError
            raise e
