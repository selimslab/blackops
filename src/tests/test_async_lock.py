import asyncio
from dataclasses import dataclass, field

import async_timeout

from src.periodic import StopwatchContext, lock_with_timeout


@dataclass
class Test:
    order_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def order(self, i):
        lock = self.order_lock
        if lock.locked():
            return f"order_in_progress", i
        async with lock_with_timeout(lock, 0.2):
            return i


async def robot(name, t, sleep):
    await asyncio.sleep(sleep)
    name = f"r-{name}"
    ok = 0
    for i in range(10):
        res = await t.order(i)
        if res == i:
            ok += 1
        await asyncio.sleep(0.1)  # random.randint(1, 2) * 0.1
    print(name, ok)


async def test_order_lock():

    t = Test()
    aws = [robot(i, t, 0.01) for i in range(9)]  # random.randint(0, 1))
    await asyncio.gather(*aws)


if __name__ == "__main__":
    asyncio.run(test_order_lock())
