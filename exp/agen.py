import asyncio 
import itertools
from aiostream import stream
import aiostream 
from aiostream import stream, async_

async def gen():
    for i in itertools.count(0):
        yield i 
        await asyncio.sleep(1)

async def gen2():
    for i in itertools.count(1000):
        yield i 
        await asyncio.sleep(1)


async def st():
    xs = stream.zip(gen(), gen2())
    # ys = stream.map(xs, async_(lambda ms: asyncio.sleep(ms / 1000)))
    ys = stream.switchmap(xs, async_(lambda s1, s2: asyncio.sleep(1) ))
    zs = stream.spaceout(ys, 1)

    async with zs.stream() as streamer:

        # Asynchronous iteration
        async for z in streamer:
            print(z)

async def consumer():
    async for i in gen():
        print(i)
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(consumer())