import asyncio
from typing import Callable

import blackops.pubsub.pub as pub
from blackops.util.logger import logger


async def periodic(func: Callable, sleep_seconds: float) -> None:
    while True:
        try:
            await func()
        except Exception as e:
            logger.error(f"periodic: {e}")
        finally:
            await asyncio.sleep(sleep_seconds)
