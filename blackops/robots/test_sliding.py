import asyncio
from dataclasses import asdict
from datetime import datetime
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
from blackops.streams.test_bt import create_bt_test_generator
from blackops.util.hash import dict_to_hash


async def test_max_usable():
    stg = SlidingWindowConfig(
        base="ETH",
        quote="USDT",
        base_step_qty=5,
        max_usable_quote_amount_y=100,
        credit=Decimal("0.0012"),
        step_constant_k=Decimal("0.0004"),
        use_real_money=False,
        testnet=True,
    )

    robot = create_trader_from_strategy(stg)

    bt_test_data = [
        431,
        {
            "CS": 1144463,
            "PS": "ETHUSDT",
            "AO": [
                {"A": "1.329", "P": "3775.2"},
                {"A": "0.09253216", "P": "3782.3"},
                {"A": "13.24959588", "P": "3773.7"},
            ],
            "BO": [
                {"A": "0.1854", "P": "3775.1"},
                {"A": "0.3345592", "P": "3775"},
                {"A": "13.24959588", "P": "3773.7"},
            ],
        },
    ]

    robot.follower_book_stream = create_bt_test_generator(bt_test_data)
    robot.leader_book_ticker_stream = test_bn_generator()

    # try:
    #     async with timeout(8):
    #         await robot.run()
    # except asyncio.TimeoutError as e:
    #     pass


async def test_run():
    stg = SlidingWindowConfig(
        base="ETH",
        quote="USDT",
        base_step_qty=5,
        max_usable_quote_amount_y=100,
        credit=Decimal("0.0012"),
        step_constant_k=Decimal("0.0004"),
        use_real_money=False,
        testnet=True,
    )
    pprint(stg)
    pprint(stg.dict())
    pprint(json.dumps(stg.dict()))

    stg.is_valid()

    # hash all but sha field, which is used as the key
    sha = dict_to_hash(stg.dict(exclude={"sha", "created_at"}))[:7]

    stg.sha = sha
    stg.created_at = str(datetime.now().isoformat())

    deserialized_config = SlidingWindowConfig(**json.loads(json.dumps(stg.dict())))

    robot = create_trader_from_strategy(deserialized_config)

    # pprint(robot)

    await robot.update_balances()

    pprint(robot.pair)

    assert robot.current_step == 0

    await robot.update_balances()

    assert robot.pair.base.balance == 0
    assert robot.pair.quote.balance == robot.max_usable_quote_amount_y

    assert robot.current_step == 0

    # robot.follower_book_stream = test_bt_generator()
    # robot.leader_book_ticker_stream = test_bn_generator()

    try:
        async with timeout(8):
            await robot.run()
    except asyncio.TimeoutError as e:
        pass

    # assert robot.pair.base.balance == Decimal("0.3")
    # assert robot.pair.quote.balance == Decimal("8865.40")
    # assert len(robot.orders) == 3

    have_usable_balance = robot.have_usable_balance()

    pprint(robot)


async def test_serialize():
    stg = SlidingWindowConfig(
        base="ETH",
        quote="USDT",
        base_step_qty=5,
        max_usable_quote_amount_y=100,
        credit=Decimal("0.0012"),
        step_constant_k=Decimal("0.0004"),
        use_real_money=False,
        testnet=True,
    )
    robot = create_trader_from_strategy(stg)

    print(asdict(robot))


if __name__ == "__main__":
    asyncio.run(test_run())
