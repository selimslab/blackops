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
class SingleTaskContext:
    task: Optional[asyncio.Task] = None

    @asynccontextmanager
    async def refresh_task(self, func):
        try:
            if self.task:
                self.task.cancel()
            yield
        finally:
            self.task = asyncio.create_task(func())
