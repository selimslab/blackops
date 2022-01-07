import asyncio
import collections
import random
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

    async def order(self, i):
        if self.order_lock.locked():
            return f"order_in_progress", i
        async with self.timed_order_context():
            return i


async def robot(name, t, sleep):
    await asyncio.sleep(sleep)
    name = f"r-{name}"
    for i in range(10):
        res = await t.order(f"{name} {i}")
        print(res)
        await asyncio.sleep(0.2)


async def test_order_lock():
    t = Test()
    aws = [robot(i, t, random.randint(0, 1)) for i in range(10)]
    await asyncio.gather(*aws)


if __name__ == "__main__":
    asyncio.run(test_order_lock())