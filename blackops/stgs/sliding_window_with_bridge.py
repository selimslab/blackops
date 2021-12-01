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

    async def run_streams(self):
        logger.info(f"Start streams for {self.name}")

        consumers: Any = [
            self.watch_books_and_decide(),
            self.update_bridge_quote(),
            self.update_best_buyers_and_sellers(),
            self.broadcast_stats_periodical(),
        ]  # is this ordering important ?

        await asyncio.gather(*consumers)

    def get_mid(self, book: dict) -> Optional[Decimal]:
        base_bridge_pair_mid = super().get_mid(book)
        if base_bridge_pair_mid and self.bridge_quote:
            return base_bridge_pair_mid * self.bridge_quote
        return None

    async def update_bridge_quote(self):
        if not self.leader_bridge_quote_stream:
            raise ValueError("No bridge quote stream")

        async for book in self.leader_bridge_quote_stream:
            new_quote = super().get_mid(book)
            if new_quote:
                self.bridge_quote = new_quote
                self.bridge_last_updated = datetime.now().time()
            await asyncio.sleep(0)

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
