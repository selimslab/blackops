import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Callable, Optional

import async_timeout

from src.monitoring import logger


async def periodic(func: Callable, sleep_seconds: float) -> None:
    while True:
        try:
            await func()
        except Exception as e:
            logger.error(f"periodic: {e}")
        finally:
            await asyncio.sleep(sleep_seconds)


@asynccontextmanager
async def timer_lock(lock: asyncio.Lock, sleep: float):
    # try:
    #     async with async_timeout.timeout(sleep):
    #         async with lock:
    #             yield
    #             await asyncio.sleep(0)
    # except asyncio.TimeoutError:
    #     pass

    # async with lock:
    #     try:
    #         async with async_timeout.timeout(sleep):
    #             yield
    #             await asyncio.sleep(0)
    #     except asyncio.TimeoutError:
    #         pass

    async with lock:
        yield
        await asyncio.sleep(sleep)

    # async with lock:
    #     try:
    #         async with async_timeout.timeout(sleep):
    #             yield
    #             await asyncio.sleep(0)
    #     except asyncio.TimeoutError:
    #         pass

    # try:
    #     async with async_timeout.timeout(sleep):
    #         async with lock:
    #             yield
    # except asyncio.TimeoutError:
    #     pass


@dataclass
class StopwatchContext:
    task: Optional[asyncio.Task] = None

    async def call_after(self, func: Callable, seconds: float) -> None:
        await asyncio.sleep(seconds)
        func()

    @asynccontextmanager
    async def stopwatch(self, func: Callable, seconds: float):
        """Cancel the old task when the new arrives"""
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.call_after(func, seconds))
        yield
        await asyncio.sleep(0)
