from blackops.api.models.stg import SlidingWindow, SlidingWindowWithBridge, Strategy
from blackops.domain.models.asset import Asset, AssetPair
from blackops.exchanges.binance.factory import binance_client_testnet
from blackops.exchanges.btcturk.factory import (
    btcturk_client_real,
    create_testnet_client,
)
from blackops.stgs.sliding_window import SlidingWindowTrader
from blackops.stgs.sliding_window_with_bridge import SlidingWindowWithBridgeTrader
from blackops.streams.binance import create_book_stream_binance
from blackops.streams.btcturk import create_book_stream_btcturk
from blackops.util.logger import logger

# from decimal import getcontext
# getcontext().prec = 10

TESTNET = "testnet"
REAL = "real"

BINANCE = "binance"
BTCTURK = "btcturk"

EXCHANGES = {
    BINANCE: {TESTNET: binance_client_testnet, REAL: binance_client_testnet},
    BTCTURK: {REAL: btcturk_client_real},
}

SLIDING_WINDOW = "sliding_window"
SLIDING_WINDOW_WITH_BRIDGE = "sliding_window_with_bridge"

TRADER_CLASSES = {
    SLIDING_WINDOW: SlidingWindowTrader,
    SLIDING_WINDOW_WITH_BRIDGE: SlidingWindowWithBridgeTrader,
}


def create_leader_exchange_client(stg: Strategy):
    network = TESTNET if stg.testnet else REAL
    exchange = EXCHANGES.get(stg.leader_exchange, {}).get(network)
    if not exchange:
        raise ValueError(f"unknown leader exchange: {stg.leader_exchange}")
    return exchange


def create_followers_exchange_client(stg: Strategy):
    network = TESTNET if stg.testnet else REAL
    if network == TESTNET:
        exchange = create_testnet_client({stg.quote: stg.max_usable_quote_amount_y})
    else:
        exchange = EXCHANGES.get(stg.follower_exchange, {}).get(network)

    if not exchange:
        raise ValueError(f"unknown follower exchange: {stg.follower_exchange}")
    return exchange


def sliding_window_with_bridge_factory(stg: Strategy):
    if not isinstance(stg, SlidingWindowWithBridge):
        raise ValueError(f"unknown strategy type: {stg.type}")

    bridge: str = stg.bridge
    if not bridge:
        raise ValueError(f"bridge is not set for strategy: {stg}")

    leader_exchange_client = create_leader_exchange_client(stg)
    followers_exchange_client = create_followers_exchange_client(stg)

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    bridge_quote_symbol = bridge + stg.quote
    base_bridge_symbol = stg.base + bridge

    trader = SlidingWindowWithBridgeTrader(
        bridge=Asset(bridge),
        leader_exchange=leader_exchange_client,
        follower_exchange=followers_exchange_client,
        pair=pair,
        max_usable_quote_amount_y=stg.max_usable_quote_amount_y,
        step_count=stg.step_count,
        credit=stg.credit,
        step_constant_k=stg.step_constant_k,
        leader_book_ticker_stream=create_book_stream_binance(base_bridge_symbol),
        leader_bridge_quote_stream=create_book_stream_binance(bridge_quote_symbol),
        follower_book_stream=create_book_stream_btcturk(pair.symbol),
    )

    return trader


def sliding_window_factory(stg: Strategy):

    leader_exchange_client = create_leader_exchange_client(stg)
    followers_exchange_client = create_followers_exchange_client(stg)

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    trader = SlidingWindowTrader(
        leader_exchange=leader_exchange_client,
        follower_exchange=followers_exchange_client,
        pair=pair,
        max_usable_quote_amount_y=stg.max_usable_quote_amount_y,
        step_count=stg.step_count,
        credit=stg.credit,
        step_constant_k=stg.step_constant_k,
        leader_book_ticker_stream=create_book_stream_binance(pair.symbol),
        follower_book_stream=create_book_stream_btcturk(pair.symbol),
    )

    return trader


FACTORIES = {
    SLIDING_WINDOW: sliding_window_factory,
    SLIDING_WINDOW_WITH_BRIDGE: sliding_window_with_bridge_factory,
}


def create_trader_from_strategy(stg: dict):
    logger.info(stg)
    stg_type = stg.get("type")
    if not stg_type:
        raise ValueError(f"strategy type is not set: {stg}")

    if stg_type == SLIDING_WINDOW:
        stg = SlidingWindow(**stg)  # type: ignore
    elif stg_type == SLIDING_WINDOW_WITH_BRIDGE:
        stg = SlidingWindowWithBridge(**stg)  # type: ignore
    else:
        raise ValueError(f"unknown strategy type: {stg_type}")

    STRATEGY_CLASS = TRADER_CLASSES.get(stg_type)

    if not STRATEGY_CLASS:
        raise ValueError(f"unknown strategy type: {stg_type}")

    factory_func = FACTORIES.get(stg_type)
    if not factory_func:
        raise ValueError(f"unknown factory function for strategy type: {stg_type}")

    trader = factory_func(stg)
    return trader
