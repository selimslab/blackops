from typing import Callable

import blackops.streams.bn as bn_streams
import blackops.streams.btcturk as btc_streams
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.factory import ExchangeType, NetworkType, create_api_client
from blackops.robots.config import SlidingWindowConfig, StrategyConfig, StrategyType
from blackops.robots.sliding import SlidingWindowTrader
from blackops.util.logger import logger

Robot = SlidingWindowTrader  # union type


def sliding_window_factory(stg: SlidingWindowConfig):
    if not isinstance(stg, SlidingWindowConfig):
        raise ValueError(f"wrong strategy type: {stg.type}")

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")
    pub_channel = stg.sha

    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL

    follower_exchange: ExchangeBase = create_api_client(
        ExchangeType(stg.follower_exchange), network
    )  # type:ignore

    if network == NetworkType.TESTNET and follower_exchange:
        follower_exchange.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), stg.max_usable_quote_amount_y * 3
        )

    leader_exchange: ExchangeBase = create_api_client(
        ExchangeType(stg.leader_exchange), network
    )  # type:ignore

    pair = AssetPair(Asset(symbol=stg.base), Asset(symbol=stg.quote))

    bridge_symbol = stg.bridge
    bridge_exchange = None
    bridge_stream = None

    if bridge_symbol:
        base_bridge_symbol = stg.base + bridge_symbol
        bridge_quote_symbol = bridge_symbol + stg.quote

        leader_book_stream = bn_streams.create_book_stream(
            base_bridge_symbol, pub_channel
        )

        bridge_stream_factory_func = create_bridge_stream(
            ExchangeType(stg.leader_exchange)
        )
        bridge_stream = bridge_stream_factory_func(bridge_quote_symbol, pub_channel)

        if stg.bridge_exchange is ExchangeType.BINANCE:
            bridge_exchange = leader_exchange
        elif stg.bridge_exchange is ExchangeType.BTCTURK:
            bridge_exchange = follower_exchange

    else:
        leader_book_stream = bn_streams.create_book_stream(pair.symbol, pub_channel)

    follower_book_stream = btc_streams.create_book_stream(pair.symbol, pub_channel)

    trader = SlidingWindowTrader(
        config=stg,
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
        bridge_exchange=bridge_exchange,
        leader_book_stream=leader_book_stream,
        follower_book_stream=follower_book_stream,
        bridge_stream=bridge_stream,
    )

    return trader


BRIDGE_STREAM_FACTORIES = {
    ExchangeType.BINANCE: bn_streams.create_book_stream,
    ExchangeType.BTCTURK: btc_streams.create_book_stream,
}


def create_bridge_stream(ex_type: ExchangeType) -> Callable:
    factory_func = BRIDGE_STREAM_FACTORIES.get(ex_type)

    if not factory_func:
        raise ValueError(f"unknown exchange: {ex_type}")

    return factory_func


FACTORIES = {
    StrategyType.SLIDING_WINDOW: sliding_window_factory,
}


def create_trader_from_strategy(stg: StrategyConfig) -> Robot:
    try:
        stg.is_valid()
        factory_func = FACTORIES[StrategyType(stg.type)]
        robot = factory_func(stg)
        return robot
    except Exception as e:
        logger.error(f"create_trader_from_strategy: {e}")
        raise e
