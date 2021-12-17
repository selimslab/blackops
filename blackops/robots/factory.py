import blackops.streams.bn as bn_streams
import blackops.streams.btcturk as btc_streams
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.factory import ExchangeType, NetworkType, create_exchange
from blackops.robots.base import RobotBase
from blackops.robots.config import (
    STRATEGY_CLASS,
    SlidingWindowConfig,
    StrategyConfig,
    StrategyType,
)
from blackops.robots.sliding import SlidingWindowTrader
from blackops.taskq.redis import STREAM_MAP, async_redis_client
from blackops.util.logger import logger


async def sliding_window_factory(stg: SlidingWindowConfig):
    if not isinstance(stg, SlidingWindowConfig):
        raise ValueError(f"wrong strategy type: {stg.type}")

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")
    pub_channel = stg.sha

    network = NetworkType(stg.testnet)

    follower_exchange: ExchangeBase = create_exchange(
        ExchangeType(stg.follower_exchange), network
    )  # type:ignore

    if network == NetworkType.TESTNET and follower_exchange:
        await follower_exchange.test_exchange.add_balance(  # type:ignore
            stg.quote, stg.max_usable_quote_amount_y
        )

    leader_exchange: ExchangeBase = create_exchange(
        ExchangeType(stg.leader_exchange), network
    )  # type:ignore

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    bridge_symbol = stg.bridge
    if bridge_symbol:
        bridge_quote_symbol = bridge_symbol + stg.quote
        base_bridge_symbol = stg.base + bridge_symbol

        leader_book_ticker_stream = bn_streams.create_book_stream(
            base_bridge_symbol, pub_channel
        )
        leader_bridge_quote_stream = bn_streams.create_book_stream(
            bridge_quote_symbol, pub_channel
        )
    else:
        leader_book_ticker_stream = bn_streams.create_book_stream(
            pair.symbol, pub_channel
        )
        leader_bridge_quote_stream = None

    follower_book_stream = btc_streams.create_book_stream(pair.symbol, pub_channel)

    trader = SlidingWindowTrader(
        sha=stg.sha,
        bridge_symbol=bridge_symbol,
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


FACTORIES = {
    StrategyType.SLIDING_WINDOW: sliding_window_factory,
}


async def create_trader_from_strategy(stg: StrategyConfig) -> RobotBase:
    try:
        stg.is_valid()
        factory_func = FACTORIES[StrategyType(stg.type)]
        robot = await factory_func(stg)
        return robot
    except ValueError:
        raise ValueError(f"unknown strategy type: {stg.type}")
