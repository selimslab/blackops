

import asyncio
import collections
import json
import operator
import pprint
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable, List, Optional

from aiostream import async_, stream

from blackops.clients.binance.stream import ws_generator_binance
from blackops.clients.btcturk.main import Client, btcturk_client
from blackops.clients.btcturk.stream import ws_generator_bt
from blackops.domain.models import Asset, AssetPair, Exchange, LeaderFollowerStrategy
from blackops.logger import logger
from blackops.util import decimal_division, decimal_mid

from .stg import SlidingWindows

@dataclass
class SlidingWindowsWithBridge(SlidingWindows):
    bridge: Asset = Asset("none")

    def init_bridge(self):
        self.bridge_base_pair = AssetPair(self.pair.base, self.bridge)
        self.bridge_quote_pair = AssetPair(self.bridge, self.pair.quote)
        self.bridge_quote = Decimal(1)


    def start(self):
        self.init_bridge()

    def get_window_mid(self, order_book: dict) -> Optional[Decimal]:
        mid = self.leader_exchange.get_mid(order_book)
        if mid:
             # bridge_quote for bridging, xusdt -> usdtry -> xtry
            return mid * self.bridge_quote



