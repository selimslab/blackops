import asyncio
import websockets
import json 

async def gen():
    uri = "wss://ws-feed-pro.btcturk.com/"
    message = [
        151,
        {"type": 151, "channel": "orderbook", "event": 'USDTTRY', "join": True},
    ]
    message = json.dumps(message)

    async with websockets.connect(uri=uri) as websocket:
        while True:
            await websocket.send(message)
            data = await websocket.recv()
            yield data


async def hello():
    async for i in gen():
        print(i)

if __name__ == "__main__":
    asyncio.run(hello())