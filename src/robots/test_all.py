import asyncio
from decimal import Decimal

import pytest
import pytest_asyncio

from src.domain import Asset, AssetPair, create_asset_pair
from src.monitoring import logger
from src.pubsub.radio import radio
from src.robots import robot_api
from src.robots.factory import Robot, robot_factory
from src.robots.sliding.main import TargetPrices, Targets
from src.robots.sliding.market import MarketPrices
from src.robots.sliding.orders import OrdersDelivered
from src.stgs import StrategyConfig, StrategyInput, strategy_api


async def create_config_w_bridge():
    stg_in = StrategyInput(base="ATOM", quote="TRY", bridge="USDT", use_bridge=True)
    config = await strategy_api.create_stg(stg_in)
    return config


async def create_config():
    stg_in = StrategyInput(base="ETH", quote="USDT")
    config = await strategy_api.create_stg(stg_in)
    return config


async def get_robot():
    return robot_factory.create_robot(await create_config())


@pytest.mark.asyncio
async def test_end_to_end():

    config = await create_config()

    res = await strategy_api.get_stg(config.sha)
    assert res.input == config.input

    assert robot_api.get_tasks() == []

    assert radio.get_stations() == []

    ###########

    # @pytest.mark.asyncio
    # async def test_bid_ask():

    asks = [
        {"A": "1.329", "P": "3775.2"},
        {"A": "0.09253216", "P": "3782.3"},
        {"A": "13.24959588", "P": "3773.7"},
    ]

    bids = [
        {"A": "0.1854", "P": "3775.1"},
        {"A": "0.3345592", "P": "3775"},
        {"A": "13.24959588", "P": "3773.7"},
    ]

    expected = [
        MarketPrices(bid=Decimal("3775.1"), ask=Decimal("3775.2")),
        MarketPrices(bid=Decimal("3775"), ask=Decimal("3782.3")),
        MarketPrices(bid=Decimal("3773.7"), ask=Decimal("3773.7")),
    ]

    robot = await get_robot()

    book = {}
    for i, (a, b, exp) in enumerate(zip(asks, bids, expected)):
        book["AO"] = [a]
        book["BO"] = [b]

        await robot.follower.update_prices(book)
        assert robot.follower.prices == exp
        await asyncio.sleep(0.1)
        assert robot.follower.prices == exp
        await asyncio.sleep(0.2)
        assert robot.follower.prices == exp
        await asyncio.sleep(0.1)
        assert robot.follower.prices == MarketPrices(bid=None, ask=None)

    ###########

    bn_books = [
        {
            "stream": "ethusdt@bookTicker",
            "data": {
                "u": 13813384574,
                "s": "ETHUSDT",
                "b": "2956.50000000",
                "B": "4.26930000",
                "a": "2956.51000000",
                "A": "4.85550000",
            },
        },
        {
            "stream": "ethusdt@bookTicker",
            "data": {
                "u": 13813384579,
                "s": "ETHUSDT",
                "b": "2957.50000000",
                "B": "1.86930000",
                "a": "2957.54000000",
                "A": "4.85550000",
            },
        },
        {
            "stream": "ethusdt@bookTicker",
            "data": {
                "u": 13813384583,
                "s": "ETHUSDT",
                "b": "2958.32000000",
                "B": "1.86930000",
                "a": "2956.63000000",
                "A": "6.85550000",
            },
        },
    ]

    expected = [
        Targets(
            maker=TargetPrices(buy=Decimal("2952.66154"), sell=Decimal("2960.34846")),
            taker=TargetPrices(buy=Decimal("2949.11374"), sell=Decimal("2963.89626")),
            bridge=None,
        ),
        Targets(
            maker=TargetPrices(buy=Decimal("2953.67522"), sell=Decimal("2961.36478")),
            taker=TargetPrices(buy=Decimal("2950.12620"), sell=Decimal("2964.91380")),
            bridge=None,
        ),
        Targets(
            maker=TargetPrices(buy=Decimal("2953.63028"), sell=Decimal("2961.31972")),
            taker=TargetPrices(buy=Decimal("2950.08131"), sell=Decimal("2964.86869")),
            bridge=None,
        ),
    ]

    for book, exp in zip(bn_books, expected):
        robot.calculate_window(book)
        assert robot.targets == exp

    # test dummy exchange
    await robot.balance_pub.ask_balance()
    await robot.follower.update_balances()
    assert robot.follower.pair == AssetPair(
        base=Asset(symbol="ETH", free=Decimal("0"), locked=Decimal("0")),
        quote=Asset(symbol="USDT", free=Decimal("30000"), locked=Decimal("0")),
    )

    await robot.follower.long(Decimal(3000))
    assert robot.follower.order_api.orders_delivered == OrdersDelivered(buy=1, sell=0)

    await robot.balance_pub.ask_balance()
    await robot.follower.update_balances()
    assert robot.follower.pair == AssetPair(
        base=Asset(symbol="ETH", free=Decimal("0.5"), locked=Decimal("0")),
        quote=Asset(symbol="USDT", free=Decimal("28500.00"), locked=Decimal("0")),
    )

    await robot.follower.short(Decimal(4000))
    assert robot.follower.order_api.orders_delivered == OrdersDelivered(buy=1, sell=1)
    await robot.follower.short(Decimal(4000))
    assert robot.follower.order_api.orders_delivered == OrdersDelivered(buy=1, sell=1)

    await robot.balance_pub.ask_balance()
    await robot.follower.update_balances()
    assert robot.follower.pair == AssetPair(
        base=Asset(symbol="ETH", free=Decimal("0"), locked=Decimal("0")),
        quote=Asset(symbol="USDT", free=Decimal("30500.00"), locked=Decimal("0")),
    )

    # print(pformat(vars(robot), indent=4, width=1))

    # coros = robot_factory.create_coros(robot)

    # await asyncio.sleep(2)

    # assert len(coros) == 2

    # task = asyncio.create_task(robot_api.run_task(res))

    # assert robot_api.get_tasks() == [config.sha]

    # pprint(radio.get_stations())

    # await robot_api.stop_task(config.sha)


def bt_stream():
    bt_test_data = [
        431,
        {
            "CS": 1144463,
            "PS": "ETHUSDT",
            "AO": [],
            "BO": [],
        },
    ]

    asks = [
        {"A": "1.329", "P": "3775.2"},
        {"A": "0.09253216", "P": "3782.3"},
        {"A": "13.24959588", "P": "3773.7"},
    ]
    bids = [
        {"A": "0.1854", "P": "3775.1"},
        {"A": "0.3345592", "P": "3775"},
        {"A": "13.24959588", "P": "3773.7"},
    ]

    for a, b in zip(asks, bids):
        data = bt_test_data[:][1]
        data["AO"] = [a]
        data["BO"] = [b]
        yield data


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

if __name__ == "__main__":
    asyncio.run(test_end_to_end())