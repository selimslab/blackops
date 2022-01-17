import asyncio

from src.periodic.main import lock_with_timeout

lock = asyncio.Lock()


async def robot():
    async with lock_with_timeout(lock, 0.1) as ok:
        if ok:
            print("ok", lock.locked())
        else:
            print("no", lock.locked())

        # await asyncio.sleep(0.)


async def test_timer_lock():
    await asyncio.gather(robot(), robot(), robot())


if __name__ == "__main__":
    asyncio.run(test_timer_lock())
