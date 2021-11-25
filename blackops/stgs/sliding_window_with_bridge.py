import asyncio
import itertools
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Optional

import blackops.pubsub.pub as pub
from blackops.domain.models.asset import Asset
from blackops.util.logger import logger

from .sliding_window import SlidingWindowTrader


@dataclass
class SlidingWindowWithBridgeTrader(SlidingWindowTrader):
    bridge: Asset = Asset("")

    leader_bridge_quote_stream: Optional[AsyncGenerator] = None

    bridge_quote: Optional[Decimal] = None

    bridge_last_updated: Optional[Any] = None

    name: str = "Sliding Window With Bridge"

    def get_mid(self, book: dict) -> Optional[Decimal]:
        mid = super().get_mid(book)
        if mid and self.bridge_quote:
            return mid * self.bridge_quote
        return None

    def create_stats_message(self):
        message = super().create_stats_message()
        message["bridge"] = str(self.bridge_quote)
        message["bridge_last_updated"] = str(self.bridge_last_updated)
        return message

    @staticmethod
    async def alternating_stream(gens):
        for (gen, func) in itertools.cycle(gens):
            book = await gen.__anext__()
            if book:
                yield func, book

    async def watch_books_and_decide(self):
        msg = f"Watching books from {self.leader_exchange.name}"
        logger.info(msg)
        pub.publish_message(self.channnel, msg)
        gens = [
            (self.leader_book_ticker_stream, self.update_theo),
            (self.leader_bridge_quote_stream, self.update_bridge_quote),
        ]

        async for func, book in self.alternating_stream(gens):
            await func(book)
            await asyncio.sleep(0.001)

    async def update_theo(self, book):
        self.binance_book_ticker_stream_seen += 1
        self.calculate_window(book)
        await self.should_transact()

    async def update_bridge_quote(self, book):
        new_quote = super().get_mid(book)
        if new_quote:
            self.bridge_quote = new_quote
            self.bridge_last_updated = datetime.now().time()
