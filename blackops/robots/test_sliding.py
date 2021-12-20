import asyncio
from decimal import Decimal
from pprint import pprint

import simplejson as json
from async_timeout import timeout

from blackops.exchanges.factory import ExchangeType, NetworkType, create_exchange
from blackops.robots.config import (
    STRATEGY_CLASS,
    SlidingWindowConfig,
    StrategyConfig,
    StrategyType,
)
from blackops.robots.factory import create_trader_from_strategy
from blackops.streams.test_bn import test_bn_generator
from blackops.streams.test_bt import test_bt_generator


async def test():
    stg = SlidingWindowConfig(
        base="XRP",
        quote="USDT",
        base_step_qty=15,
        max_usable_quote_amount_y=100,
        credit=Decimal("0.0012"),
        step_constant_k=Decimal("0.0004"),
        use_real_money=True,
        testnet=False,
    )

    pprint(stg)
    pprint(stg.dict())
    pprint(json.dumps(stg.dict()))

    deserialized_config = SlidingWindowConfig(**json.loads(json.dumps(stg.dict())))

    robot = create_trader_from_strategy(deserialized_config)

    # pprint(robot)

    # await robot.update_balances()

    # pprint(robot.pair)

    # assert robot.current_step == 0

    # await robot.update_balances()

    # assert robot.pair.base.balance == 0
    # assert robot.pair.quote.balance == robot.max_usable_quote_amount_y

    # assert robot.current_step == 0

    # robot.follower_book_stream = test_bt_generator()
    # robot.leader_book_ticker_stream = test_bn_generator()

    # try:
    #     async with timeout(8):
    #         await robot.run()
    # except asyncio.TimeoutError as e:
    #     assert robot.pair.base.balance == Decimal("0.3")
    #     assert robot.pair.quote.balance == Decimal("8865.40")
    #     assert len(robot.orders) == 3

    await robot.run()


if __name__ == "__main__":
    asyncio.run(test())
