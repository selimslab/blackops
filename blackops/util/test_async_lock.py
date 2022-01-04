import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class Test:
    order_lock = asyncio.Lock()

    @asynccontextmanager
    async def timed_order_context(self):
        async with self.order_lock:
            yield
            await asyncio.sleep(0.1)
        # try:
        #     lock = self.order_lock.acquire(timeout=0.1)
        #     if lock:
        #          yield
        # finally:
        #     self.order_lock.release()

        # try:
        #     yield
        #     self.order_in_progress = True
        #     await asyncio.sleep(0.5)
        # finally:
        #     self.order_in_progress = False

    async def order(self, i):
        if self.order_lock.locked():
            return f"order_in_progress", i
        async with self.timed_order_context():
            return i


async def robot(name, t):
    for i in range(10):
        res = await t.order(f"{name} {i}")
        print(res)
        await asyncio.sleep(0.03)


async def test_order_lock():
    t = Test()

    # async def robot2():
    #     for i in range(10):
    #         await t.order()
    #         # await asyncio.sleep(0.05)

    aws = asyncio.gather(robot("x", t), robot("y", t))
    await aws


if __name__ == "__main__":
    asyncio.run(test_order_lock())
