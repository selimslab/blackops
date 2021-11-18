from blackops.api.models.stg import Strategy
from blackops.domain.models.asset import Asset, AssetPair
from blackops.exchanges.binance.factory import binance_client_testnet
from blackops.exchanges.btcturk.factory import (
    btcturk_client_real,
    create_testnet_client,
)
from blackops.stgs.sliding_window import SlidingWindow
from blackops.stgs.sliding_window_with_bridge import SlidingWindowsWithBridge
from blackops.streams.binance import create_book_stream_binance
from blackops.streams.btcturk import create_book_stream_btcturk

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

STRATEGY_CLASSES = {
    SLIDING_WINDOW: SlidingWindow,
    SLIDING_WINDOW_WITH_BRIDGE: SlidingWindowsWithBridge,
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
    bridge: str = stg.bridge
    if not bridge:
        raise ValueError(f"bridge is not set for strategy: {stg}")

    leader_exchange_client = create_leader_exchange_client(stg)
    followers_exchange_client = create_followers_exchange_client(stg)

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    bridge_quote_symbol = bridge + stg.quote
    base_bridge_symbol = stg.base + bridge

    trader = SlidingWindowsWithBridge(
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

    trader = SlidingWindow(
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


def create_trader_from_strategy(stg: Strategy):

    STRATEGY_CLASS = STRATEGY_CLASSES.get(stg.type)

    if not STRATEGY_CLASS:
        raise ValueError(f"unknown strategy type: {stg.type}")

    factory_func = FACTORIES.get(stg.type)
    if not factory_func:
        raise ValueError(f"unknown factory function for strategy type: {stg.type}")

    trader = factory_func(stg)
    return trader
