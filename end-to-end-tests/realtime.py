import asyncio
from decimal import Decimal

import blackops.domain.symbols as symbols
from blackops.robots.factory import create_trader_from_strategy
from blackops.robots.config import SlidingWindowConfig



async def test_sliding():

    # await asyncio.gather(trader.run())
    pass 



if __name__ == "__main__":
    asyncio.run(test_sliding())
