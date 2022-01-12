import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class Test:
    order_lock = asyncio.Lock()

    @asynccontextmanager
    async def timed_order_context(self, lock):
        async with lock:
            yield
            await asyncio.sleep(0.16)

    async def order(self, i):
        lock = self.order_lock
        if lock.locked():
            return f"order_in_progress", i
        async with self.timed_order_context(lock):
            return i


async def robot(name, t, sleep):
    await asyncio.sleep(sleep)
    name = f"r-{name}"
    ok = 0
    for i in range(5):
        res = await t.order(i)
        if res == i:
            ok += 1
        await asyncio.sleep(0.1) # random.randint(1, 2) * 0.1
    print(name, ok)


async def test_order_lock():
    t = Test()
    aws = [robot(i, t, random.randint(0, 1)) for i in range(7)]
    await asyncio.gather(*aws)


if __name__ == "__main__":
    asyncio.run(test_order_lock())
