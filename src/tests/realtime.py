import asyncio
from decimal import Decimal

import src.stgs.symbols as symbols
from src.robots.factory import create_trader_from_strategy
from src.stgs.sliding.config import SlidingWindowConfig


async def test_sliding():

    # await asyncio.gather(trader.run())
    pass


if __name__ == "__main__":
    asyncio.run(test_sliding())
