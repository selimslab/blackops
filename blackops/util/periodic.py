import asyncio
from typing import Callable


async def periodic(func: Callable, sleep_seconds: float) -> None:
    while True:
        await func()
        await asyncio.sleep(sleep_seconds)
