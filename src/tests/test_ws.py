import asyncio
import random
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import async_timeout

thread_executor = ThreadPoolExecutor(max_workers=8)
proc_executor = ProcessPoolExecutor(max_workers=2)


async def leader_gen():
    i = 0
    while True:
        yield i
        i += 1
        await asyncio.sleep(0.025)


async def f_gen():
    i = 0
    while True:
        yield i
        i += 1
        await asyncio.sleep(0.2)


class Leader:
    i: int
    data: list = []

    def get_i(self):
        return sum(self.data) / len(self.data)

    async def run(self):
        async for i in leader_gen():
            self.i = i
            # self.data.append(i)
            await asyncio.sleep(0)


class Follower:

    ask: int = 0
    bid: int = 0

    async def run(self):
        async for i in f_gen():
            self.ask = -i
            await asyncio.sleep(0)


pub = Leader()
fol = Follower()


class Q:

    data: list = [i for i in range(1000000)]
    price: int = 5

    def cpu_bound(self, end):
        return sum(sorted(random.randint(0, 100) for _ in range(end)))

    async def leader_consumer(self):
        while True:
            if self.price != pub.i:
                self.price = pub.i
                print(self.price, fol.ask)
                loop = asyncio.get_running_loop()
                # self.cpu_bound(10000)
                res = await loop.run_in_executor(thread_executor, self.cpu_bound, 10000)
                # coros = [
                #     loop.run_in_executor(thread_executor, self.cpu_bound, 10000)
                #     for i in range(8)
                # ]

                # await asyncio.gather(*coros)

            await asyncio.sleep(0)

    # async def follower_consumer(self):
    #     prea = preb = None
    #     while True:
    #         if prea != fol.ask:
    #             # print(fol.ask)
    #             prea = fol.ask
    #             loop = asyncio.get_running_loop()
    #             pass
    #         # result = await loop.run_in_executor(
    #         #     executor, self.cpu_bound, 1000000)

    #         #self.cpu_bound(100000)
    #         #result = cpu_bound(100000)
    #         # print(result)

    #         await asyncio.sleep(0.01)


async def main():
    q = Q()
    async with async_timeout.timeout(5):
        await asyncio.gather(pub.run(), fol.run(), q.leader_consumer())


if __name__ == "__main__":
    asyncio.run(main())
