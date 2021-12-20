import asyncio
from pprint import pprint

import simplejson as json

from blackops.robots.config import (
    STRATEGY_CLASS,
    SlidingWindowConfig,
    StrategyConfig,
    StrategyType,
)
from blackops.robots.factory import create_trader_from_strategy


async def test():
    test_config = SlidingWindowConfig(
        base="ETH",
        quote="USDT",
        base_step_qty=1.23,
        quote_step_qty=12.43,
        max_usable_quote_amount_y=100.423453425,
        credit=0.2,
        step_constant_k=0.1,
        leader_exchange="binance",
    )

    pprint(test_config)
    pprint(test_config.dict())
    pprint(json.dumps(test_config.dict()))

    deserialized_config = SlidingWindowConfig(
        **json.loads(json.dumps(test_config.dict()))
    )

    robot = create_trader_from_strategy(deserialized_config)

    pprint(robot)

    # await robot.run()


if __name__ == "__main__":
    asyncio.run(test())
