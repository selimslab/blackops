import asyncio
from dataclasses import asdict
from enum import Enum
from typing import Optional

import blackops.domain.symbols as symbols
from blackops.domain.models import Asset, AssetPair
from blackops.exchanges.binance.factory import binance_client_testnet
from blackops.exchanges.btcturk.factory import (
    btcturk_client_real,
    btcturk_client_testnet,
)

from .sliding_window import SlidingWindow
from .sliding_window_with_bridge import SlidingWindowsWithBridge

from blackops.api.stg import Strategy

TESTNET = "testnet"
REAL = "real"

BINANCE = "binance"
BTCTURK = "btcturk"

EXCHANGES = {
    BINANCE: {TESTNET: binance_client_testnet, REAL: binance_client_testnet},
    BTCTURK: {TESTNET: btcturk_client_testnet, REAL: btcturk_client_real},
}

SLIDING_WINDOW = "sliding_window"
SLIDING_WINDOW_WITH_BRIDGE = "sliding_window_with_bridge"

STRATEGIES = {
    SLIDING_WINDOW: SlidingWindow, SLIDING_WINDOW_WITH_BRIDGE: SlidingWindowsWithBridge}
}

def sliding_window_factory(
    stg: Strategy
):
    leader_network = TESTNET if stg.testnet else REAL
    leader_exchange = EXCHANGES.get(stg.leader_exchange, {}).get(leader_network)

    follower_network = TESTNET if stg.testnet else REAL
    follower_exchange = EXCHANGES.get(stg.follower_exchange, {}).get(follower_network)

    trader = SlidingWindow(
        leader_exchange=leader_exchange,
        follower_exchange=follower_exchange,
        pair=AssetPair(Asset(stg.base), Asset(stg.quote)),


    )

def create_trader_from_strategy(
    stg: Strategy
):
    stg_type = stg.type
    
    STRATEGY_CLASS = STRATEGIES.get(stg_type)

    if not STRATEGY_CLASS:
        raise ValueError(f"unknown strategy type: {stg_type}")
    
    trader = STRATEGY_CLASS(**asdict(stg))
    return trader
