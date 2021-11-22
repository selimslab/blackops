from typing import Union

import blackops.exchanges.binance.factory as binance_factory
import blackops.exchanges.btcturk.factory as btcturk_factory
from blackops.api.models.stg import SlidingWindow, SlidingWindowWithBridge, Strategy
from blackops.domain.models.asset import Asset, AssetPair
from blackops.domain.models.exchange import ExchangeBase
from blackops.exchanges.binance.base import BinanceBase
from blackops.exchanges.btcturk.base import BtcturkBase
from blackops.exchanges.btcturk.real import btcturk_api_client_real
from blackops.exchanges.btcturk.testnet import BtcturkTestnetApiClient
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
    BINANCE: {
        TESTNET: lambda: binance_factory.create_testnet_client(),
        REAL: lambda: binance_factory.create_real_client(),
    },
    BTCTURK: {
        TESTNET: lambda api_client: btcturk_factory.create_testnet_client(api_client),
        REAL: lambda api_client: btcturk_factory.create_real_client(api_client),
    },
}

API_CLIENTS = {
    BTCTURK: {
        TESTNET: lambda: BtcturkTestnetApiClient(),
        REAL: lambda: btcturk_api_client_real,
    }
}


SLIDING_WINDOW = "sliding_window"
SLIDING_WINDOW_WITH_BRIDGE = "sliding_window_with_bridge"

TRADER_CLASSES = {
    SLIDING_WINDOW: SlidingWindowTrader,
    SLIDING_WINDOW_WITH_BRIDGE: SlidingWindowWithBridgeTrader,
}


def create_exchange(ex_type: str, network: str, api_client) -> ExchangeBase:
    factory_func = EXCHANGES.get(ex_type, {}).get(network)  # type: ignore
    if not factory_func:
        raise ValueError(f"unknown exchange: {ex_type}")

    if api_client:
        return factory_func(api_client)
    else:
        return factory_func()


def create_api_client(ex_type: str, network: str):
    factory_func = API_CLIENTS.get(ex_type, {}).get(network)
    if factory_func:
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

    follower_client = create_api_client(stg.follower_exchange, network)

    if network == TESTNET and follower_client:
        await follower_client.add_balance(  # type:ignore
            stg.quote, stg.max_usable_quote_amount_y
        )

    leader_client = create_api_client(stg.leader_exchange, network)

    follower_exchange: ExchangeBase = create_exchange(
        stg.follower_exchange, network, follower_client
    )
    leader_exchange: ExchangeBase = create_exchange(
        stg.leader_exchange, network, leader_client
    )

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    bridge_quote_symbol = bridge + stg.quote
    base_bridge_symbol = stg.base + bridge

    trader = SlidingWindowWithBridgeTrader(
        sha=stg.sha,
        bridge=Asset(bridge),
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
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


async def sliding_window_factory(stg: Strategy):

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")

    network = TESTNET if stg.testnet else REAL

    follower_client = create_api_client(stg.follower_exchange, network)

    if network == TESTNET:

        await follower_client.add_balance(  # type:ignore
            stg.quote, stg.max_usable_quote_amount_y
        )

    leader_client = create_api_client(stg.leader_exchange, network)

    follower_exchange: ExchangeBase = create_exchange(
        stg.follower_exchange, network, follower_client
    )
    leader_exchange: ExchangeBase = create_exchange(
        stg.leader_exchange, network, leader_client
    )

    pair = AssetPair(Asset(stg.base), Asset(stg.quote))

    trader = SlidingWindowTrader(
        sha=stg.sha,
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
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
