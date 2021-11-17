import asyncio
from enum import Enum
from typing import Optional

import blackops.domain.symbols as symbols
from blackops.domain.models import Asset, AssetPair
from blackops.exchanges.binance.factory import binance_client_testnet
from blackops.exchanges.binance.main import Binance
from blackops.exchanges.btcturk.factory import (
    btcturk_client_real,
    btcturk_client_testnet,
)

from .sliding_window import SlidingWindow

BINANCE = "binance"
BTCTURK = "btcturk"

EXCHANGES = {BINANCE: Binance, BTCTURK: Btcturk}

SLIDING_WINDOW = "sliding_window"

STRATEGIES = {SLIDING_WINDOW: SlidingWindow}


class Strategies(Enum):
    ...


def create_strategy(
    strategy_name: str,
    base_symbol: str,
    quote_symbol: str,
    bridge_symbol: Optional[str] = None,
):
    STRATEGY_CLASS = STRATEGIES.get(strategy_name)
    if not STRATEGY_CLASS:
        raise Exception("no such strategy")

    pair = AssetPair(Asset(base_symbol), Asset(quote_symbol))

    bridge_asset = None
    if bridge_symbol:
        bridge_asset = Asset(bridge_symbol)

    stg = STRATEGY_CLASS()
    return stg
