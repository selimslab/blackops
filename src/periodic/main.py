import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Callable, Optional

import src.pubsub.log_pub as log_pub
from src.monitoring import logger


async def periodic(func: Callable, sleep_seconds: float) -> None:
    while True:
        try:
            await func()
        except Exception as e:
            logger.error(f"periodic: {e}")
        finally:
            await asyncio.sleep(sleep_seconds)


@dataclass
class StopwatchContext:
    task: Optional[asyncio.Task] = None

    async def call_after(self, func: Callable, seconds: float) -> None:
        await asyncio.sleep(seconds)
        func()

    @asynccontextmanager
    async def stopwatch(self, func: Callable, seconds: float):
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.call_after(func, seconds))
        yield
