import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Optional

import blackops.pubsub.pub as pub
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.factory import ExchangeType
from blackops.util.logger import logger


@dataclass
class BridgeWatcher:

    bridge_exchange: Optional[ExchangeBase] = None
    bridge_stream: Optional[AsyncGenerator] = None
    bridge_last_updated = datetime.now().time()
    bridge_quote: Decimal = Decimal("1")

    async def watch_bridge(self):
        if not self.bridge_stream:
            raise ValueError("No bridge quote stream")
        if not self.bridge_exchange:
            raise ValueError("No bridge exchange")

        async for book in self.bridge_stream:
            parsed_book = self.bridge_exchange.parse_book(book)
            new_quote = self.bridge_exchange.get_mid(parsed_book)
            if new_quote:
                self.bridge_quote = new_quote
                self.bridge_last_updated = datetime.now().time()
            await asyncio.sleep(0)
