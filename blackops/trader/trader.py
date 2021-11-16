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



@dataclass
class Trader():

    async def run(self):
        aws: Any = self.get_consumers()

        # aws.append(self.periodic_report(10))  # optional 

        await asyncio.gather(*aws)
    

    # CONSUMERS
    def get_consumers(self):
        if self.bridge:
            aws = [
                self.consume_binance_orderbook_stream(self.bridge_base_pair.symbol),
                self.consume_binance_bridge_quote_stream(self.bridge_quote_pair.symbol),
                self.consume_bt_orderbook_stream(self.pair.symbol),
            ]

        else:
            aws = [
                self.consume_binance_orderbook_stream(self.pair.symbol),
                self.consume_bt_orderbook_stream(self.pair.symbol),
            ]

        return aws


    async def consume_binance_orderbook_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                await self.process_binance_order_book(binance_order_book)
                await self.should_transact()

    async def consume_binance_bridge_quote_stream(self, symbol: str):
        async for binance_order_book in ws_generator_binance(symbol):
            if binance_order_book:
                self.bridge_quote = self.get_binance_mid(binance_order_book)


