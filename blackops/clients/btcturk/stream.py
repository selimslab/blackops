import asyncio
import json

from websockets import connect
from websockets.exceptions import ConnectionClosedError


def get_orderbook_message(symbol: str):
    # obdiff
    message = [
        151,
        {"type": 151, "channel": "orderbook", "event": symbol, "join": True},
    ]
    return message


async def ws_generator_bt(symbol: str, sleep_seconds=0.5):
    uri = "wss://ws-feed-pro.btcturk.com/"
    message = get_orderbook_message(symbol)
    message = json.dumps(message)

    try:
        async with connect(uri) as websocket:
            while True:
                await websocket.send(message)
                await asyncio.sleep(sleep_seconds)
                orderbook = await websocket.recv()
                yield orderbook
    except ConnectionClosedError as e:
        print(e)
        ws_generator_bt(symbol)


# def orderbook_generator(symbol:str):

#     # asyncio.run(connect_to_ws_stream(uri, message))
#     ...
