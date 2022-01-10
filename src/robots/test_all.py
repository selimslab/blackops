import asyncio
from datetime import datetime
from decimal import Decimal
from pprint import pprint

import pytest
import pytest_asyncio

from src.robots import robot_api
from src.robots.factory import robot_factory
from src.robots.radio import radio
from src.stgs import StrategyConfig, StrategyInput, strategy_api


@pytest.mark.asyncio
async def test_end_to_end():
    stg_in = StrategyInput(base="ETH", quote="USDT", use_bridge=False)
    res = await strategy_api.create_stg(stg_in)
    config = await strategy_api.get_stg(res.sha)

    coros = robot_factory.create_coros(res)
    pprint(radio.get_stations())

    assert len(coros) == 2

    assert robot_api.get_tasks() == []

    assert radio.get_stations() == []

    # task = asyncio.create_task(robot_api.run_task(res))

    # assert robot_api.get_tasks() == [config.sha]

    pprint(radio.get_stations())

    await robot_api.stop_task(config.sha)


async def bt_stream():
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


# import simplejson as json  # type: ignore
# from async_timeout import timeout

# from src.robots.factory import create_trader_from_strategy
# from src.streams.test_bn import test_bn_generator
# from src.streams.test_bt import create_bt_test_generator
# from src.idgen import dict_to_hash


# async def test_max_usable():
#     stg = SlidingWindowConfig(
#         base="ETH",
#         quote="USDT",
#         base_step_qty=5,
#         max_usable_quote_amount_y=100,
#         credit=Decimal("0.0012"),
#         step_constant_k=Decimal("0.0004"),
#         use_real_money=False,
#         testnet=True,
#     )

#     robot = create_trader_from_strategy(stg)

#     bt_test_data = [
#         431,
#         {
#             "CS": 1144463,
#             "PS": "ETHUSDT",
#             "AO": [
#                 {"A": "1.329", "P": "3775.2"},
#                 {"A": "0.09253216", "P": "3782.3"},
#                 {"A": "13.24959588", "P": "3773.7"},
#             ],
#             "BO": [
#                 {"A": "0.1854", "P": "3775.1"},
#                 {"A": "0.3345592", "P": "3775"},
#                 {"A": "13.24959588", "P": "3773.7"},
#             ],
#         },
#     ]

#     robot.follower_book_stream = create_bt_test_generator(bt_test_data)
#     robot.leader_book_stream = test_bn_generator()


# async def test_run():
#     stg = SlidingWindowConfig(
#         base="ETH",
#         quote="USDT",
#         base_step_qty=5,
#         max_usable_quote_amount_y=100,
#         credit=Decimal("0.0012"),
#         step_constant_k=Decimal("0.0004"),
#         use_real_money=False,
#         testnet=True,
#     )

#     stg.is_valid()

#     # hash all but sha field, which is used as the key
#     sha = dict_to_hash(stg.dict(exclude={"sha", "created_at"}))[:7]

#     stg.sha = sha
#     stg.created_at = str(datetime.now().isoformat())

#     deserialized_config = SlidingWindowConfig(**json.loads(json.dumps(stg.dict())))

#     robot = create_trader_from_strategy(deserialized_config)

#     try:
#         async with timeout(8):
#             await robot.run()
#     except asyncio.TimeoutError as e:
#         pass


# async def test_serialize():
#     stg = SlidingWindowConfig(
#         base="ETH",
#         quote="USDT",
#         base_step_qty=5,
#         max_usable_quote_amount_y=100,
#         credit=Decimal("0.0012"),
#         step_constant_k=Decimal("0.0004"),
#         use_real_money=False,
#         testnet=True,
#     )

#     pprint(stg)
#     pprint(stg.dict())
#     pprint(json.dumps(stg.dict()))

#     deserialized_config = SlidingWindowConfig(**json.loads(json.dumps(stg.dict())))

#     print(deserialized_config)


# if __name__ == "__main__":
#     asyncio.run(test_serialize())
