import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Optional

import blackops.util.push_events as event
from blackops.domain.models.asset import Asset
from blackops.util.logger import logger
from blackops.util.push import channel, pusher_client

from .sliding_window import SlidingWindowTrader


@dataclass
class SlidingWindowWithBridgeTrader(SlidingWindowTrader):
    bridge: Asset = Asset("None")

    leader_bridge_quote_stream: Optional[AsyncGenerator] = None

    follower_book_stream: AsyncGenerator

    bridge_quote: Optional[Decimal] = None

    name: str = "Sliding Window With Bridge"

    async def run(self):
        message = {"start": str(self)}
        pusher_client.trigger(channel, event.update, message)
        pusher_client.trigger(channel, event.order, {"ping": "pong"})

        logger.info(message)
        logger.info(self)
        await self.set_step_info()
        await self.run_streams()

    def get_mid(self, book: dict) -> Optional[Decimal]:
        mid = super().get_mid(book)
        if mid and self.bridge_quote:
            return mid * self.bridge_quote
        return None

    async def run_streams(self):
        aws: Any = [
            self.update_bridge_quote(),
            self.update_best_buyers_and_sellers(),
            self.watch_books_and_decide(),
        ]
        await asyncio.gather(*aws)

    async def update_bridge_quote(self):
        logger.info(f"Watching the leader bridge quotes..")
        if not self.leader_bridge_quote_stream:
            raise Exception("No bridge quote stream")

        async for book in self.leader_bridge_quote_stream:
            if book:
                new_quote = super().get_mid(book)
                if new_quote != self.bridge_quote:
                    self.bridge_quote = new_quote
                    message = {
                        "time": str(datetime.now().time()),
                        "bridge": str(self.bridge_quote),
                    }
                    logger.info(message)
                    pusher_client.trigger(channel, event.update, message)
