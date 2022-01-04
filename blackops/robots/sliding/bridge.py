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

    exchange: Optional[ExchangeBase] = None
    stream: Optional[AsyncGenerator] = None
    last_updated = datetime.now().time()
    quote: Decimal = Decimal("1")

    async def watch_bridge(self):
        if not self.stream:
            raise ValueError("No bridge quote stream")
        if not self.exchange:
            raise ValueError("No bridge exchange")

        async for book in self.stream:
            new_quote = self.exchange.get_mid(book)
            if new_quote:
                self.quote = new_quote
                self.last_updated = datetime.now().time()
            await asyncio.sleep(0)
