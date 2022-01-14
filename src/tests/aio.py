import asyncio


async def hello(i):
    print("hello", i)
    await asyncio.sleep(1)
    print("world")


async def main():
    coros = [hello(i) for i in range(5)]
    await asyncio.gather(*coros)


asyncio.run(main())
