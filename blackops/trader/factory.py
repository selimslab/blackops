from typing import Union

import blackops.exchanges.binance.factory as binance_factory
import blackops.exchanges.btcturk.factory as btcturk_factory
import blackops.streams.bn as bn_streams
import blackops.streams.btcturk as btc_streams
from blackops.api.models.stg import SlidingWindow, SlidingWindowWithBridge, Strategy
from blackops.domain.models.asset import Asset, AssetPair
from blackops.domain.models.exchange import ExchangeBase
from blackops.exchanges import EXCHANGE, FOLLOWERS, LEADERS
from blackops.stgs.sliding_window import SlidingWindowTrader
from blackops.stgs.sliding_window_with_bridge import SlidingWindowWithBridgeTrader
from blackops.taskq.redis import STREAM_MAP, async_redis_client
from blackops.util.logger import logger

# from decimal import getcontext
# getcontext().prec = 10


# async def create_log_channel(sha: str):
#     await async_redis_client.sadd(LOG_CHANNELS, sha)


# async def remove_log_channel(sha: str):
#     await async_redis_client.srem(LOG_CHANNELS, sha)


TESTNET = "testnet"
REAL = "real"

BINANCE = "binance"
BTCTURK = "btcturk"

EXCHANGES = {
    BINANCE: {
        TESTNET: lambda: binance_factory.create_testnet_client(),
        REAL: lambda: binance_factory.create_real_client(),
    },
    BTCTURK: {
        TESTNET: lambda: btcturk_factory.create_testnet_client(),
        REAL: lambda: btcturk_factory.create_real_client(),
    },
}


SLIDING_WINDOW = "sliding_window"
SLIDING_WINDOW_WITH_BRIDGE = "sliding_window_with_bridge"

TRADER_CLASSES = {
    SLIDING_WINDOW: SlidingWindowTrader,
    SLIDING_WINDOW_WITH_BRIDGE: SlidingWindowWithBridgeTrader,
}


def create_exchange(ex_type: str, network: str) -> EXCHANGE:
    factory_func = EXCHANGES.get(ex_type, {}).get(network)  # type: ignore

    if not factory_func:
        raise ValueError(f"unknown exchange: {ex_type}")

    return factory_func()


async def sliding_window_with_bridge_factory(stg: Strategy):
    if not isinstance(stg, SlidingWindowWithBridge):
        raise ValueError(f"wrong strategy type: {stg.type}")

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")

    bridge: str = stg.bridge
    if not bridge:
        raise ValueError(f"bridge is not set for strategy: {stg}")

    network = TESTNET if stg.testnet else REAL

    follower_exchange: FOLLOWERS = create_exchange(
        stg.follower_exchange, network
    )  # type:ignore

    if network == TESTNET and follower_exchange:
        await follower_exchange.test_exchange.add_balance(  # type:ignore
            stg.quote, stg.max_usable_quote_amount_y
        )

    leader_exchange: LEADERS = create_exchange(
        stg.leader_exchange, network
    )  # type:ignore

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    bridge_quote_symbol = bridge + stg.quote
    base_bridge_symbol = stg.base + bridge

    pub_channel = stg.sha

    leader_book_ticker_stream = bn_streams.create_book_stream(
        base_bridge_symbol, pub_channel
    )
    leader_bridge_quote_stream = bn_streams.create_book_stream(
        bridge_quote_symbol, pub_channel
    )
    follower_book_stream = btc_streams.create_book_stream(pair.symbol, pub_channel)

    trader = SlidingWindowWithBridgeTrader(
        sha=stg.sha,
        bridge=Asset(bridge),
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
        pair=pair,
        max_usable_quote_amount_y=stg.max_usable_quote_amount_y,
        base_step_qty=stg.base_step_qty,
        credit=stg.credit,
        step_constant_k=stg.step_constant_k,
        leader_book_ticker_stream=leader_book_ticker_stream,
        leader_bridge_quote_stream=leader_bridge_quote_stream,
        follower_book_stream=follower_book_stream,
    )

    return trader


async def sliding_window_factory(stg: Strategy):

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")

    network = TESTNET if stg.testnet else REAL

    follower_exchange: FOLLOWERS = create_exchange(
        stg.follower_exchange, network
    )  # type:ignore

    if network == TESTNET and follower_exchange:
        await follower_exchange.test_exchange.add_balance(  # type:ignore
            stg.quote, stg.max_usable_quote_amount_y
        )

    leader_exchange: LEADERS = create_exchange(
        stg.leader_exchange, network
    )  # type:ignore

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    # binance_stream_channel = f"{BINANCE}_{pair.symbol}"
    # btcturk_stream_channel = f"{BTCTURK}_{pair.symbol}"

    # binance_streams = await async_redis_client.hmget(STREAM_MAP, BINANCE)
    # if pair.symbol not in binance_streams:
    #     leader_book_ticker_stream = create_book_stream_binance(pair.symbol)
    #     await async_redis_client.hset(STREAM_MAP, BINANCE,binance_stream_channel )

    # bt_streams = await async_redis_client.hmget(STREAM_MAP, BTCTURK)
    # if pair.symbol not in bt_streams:
    #     follower_book_stream = create_book_stream_btcturk(pair.symbol)
    #     await async_redis_client.hget(STREAM_MAP, BTCTURK), btcturk_stream_channel

    leader_book_ticker_stream = bn_streams.create_book_stream(pair.symbol)

    follower_book_stream = btc_streams.create_book_stream(pair.symbol)

    trader = SlidingWindowTrader(
        sha=stg.sha,
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
        pair=pair,
        max_usable_quote_amount_y=stg.max_usable_quote_amount_y,
        base_step_qty=stg.base_step_qty,
        credit=stg.credit,
        step_constant_k=stg.step_constant_k,
        leader_book_ticker_stream=leader_book_ticker_stream,
        follower_book_stream=follower_book_stream,
    )

    return trader


FACTORIES = {
    SLIDING_WINDOW: sliding_window_factory,
    SLIDING_WINDOW_WITH_BRIDGE: sliding_window_with_bridge_factory,
}


Trader = Union[SlidingWindowTrader, SlidingWindowWithBridgeTrader]


async def create_trader_from_strategy(stg_dict: dict) -> Trader:
    stg_type = stg_dict.get("type")
    if not stg_type:
        raise ValueError(f"strategy type is not set: {stg_dict}")

    if stg_type == SLIDING_WINDOW:
        stg = SlidingWindow(**stg_dict)  # type: ignore
    elif stg_type == SLIDING_WINDOW_WITH_BRIDGE:
        stg = SlidingWindowWithBridge(**stg_dict)  # type: ignore
    else:
        raise ValueError(f"unknown strategy type: {stg_type}")

    stg.is_valid()

    STRATEGY_CLASS = TRADER_CLASSES.get(stg_type)

    if not STRATEGY_CLASS:
        raise ValueError(f"unknown strategy type: {stg_type}")

    factory_func = FACTORIES.get(stg_type)
    if not factory_func:
        raise ValueError(f"unknown factory function for strategy type: {stg_type}")

    trader = await factory_func(stg)
    return trader


async def create_streams_from_strategy(stg_dict: dict) -> None:
    ...
