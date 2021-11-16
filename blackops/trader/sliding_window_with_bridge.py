import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from blackops.domain.models import Asset, AssetPair

from .sliding_window import SlidingWindows


@dataclass
class SlidingWindowsWithBridge(SlidingWindows):
    bridge: Asset = Asset("none")

    bridge_quote = Decimal(1)

    def start(self):
        self.init_bridge()

    def init_bridge(self):
        self.bridge_base_pair = AssetPair(self.pair.base, self.bridge)
        self.bridge_quote_pair = AssetPair(self.bridge, self.pair.quote)
        self.bridge_quote = Decimal(1)

    def get_window_mid(self, book: dict) -> Optional[Decimal]:
        mid = self.leader_exchange.get_mid(book)
        if mid:
            return mid * self.bridge_quote
        return None

    async def run_streams(self):

        consumers: Any = [
            self.leader_exchange.book_ticker_stream(self.bridge_base_pair.symbol),
            self.update_bridge_quote(self.bridge_quote_pair.symbol),
            self.follower_exchange.orderbook_stream(self.pair.symbol),
        ]
        # aws.append(self.periodic_report(10))  # optional
        await asyncio.gather(*consumers)

    async def update_bridge_quote(self, symbol: str):
        async for book in self.leader_exchange.book_ticker_stream(symbol):
            new_quote = self.leader_exchange.get_mid(book)
            if new_quote:
                self.bridge_quote = new_quote
