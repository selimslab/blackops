import asyncio
from decimal import Decimal
from typing import Callable, Union

import src.pubsub.pub as pub
from src.monitoring import logger


async def periodic(func: Callable, sleep_seconds: float) -> None:
    while True:
        try:
            await func()
        except Exception as e:
            logger.error(f"periodic: {e}")
        finally:
            await asyncio.sleep(sleep_seconds)
