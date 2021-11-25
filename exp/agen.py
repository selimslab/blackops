import asyncio 
import itertools
from aiostream import stream
import aiostream 
from aiostream import stream, async_

async def gen1():
    for i in itertools.count(0):
        yield i 
        await asyncio.sleep(1)

async def gen2():
    for i in itertools.count(1000):
        yield i 
        await asyncio.sleep(1)

async def anext(ait):
    return await ait.__anext__()

async def st():

    gens = [gen1(), gen2()]
    for gen in itertools.cycle(gens):
        yield await gen.__anext__()
    



# def dd():

#     xs = stream.zip(gen(), gen2())
#     # ys = stream.map(xs, async_(lambda ms: asyncio.sleep(ms / 1000)))
#     ys = stream.switchmap(xs, async_(lambda s1, s2: asyncio.sleep(1) ))
#     zs = stream.spaceout(ys, 1)

#     async with zs.stream() as streamer:

#         # Asynchronous iteration
#         async for z in streamer:
#             print(z)

async def generr():
    for i in range(19):
        yield Exception(f"Error {i}")


async def consumer():
    async for i in generr():
        print(i)


if __name__ == "__main__":
    asyncio.run(consumer())