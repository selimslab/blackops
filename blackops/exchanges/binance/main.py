from dataclasses import dataclass
from typing import AsyncIterator

from blackops.domain.models import Exchange

from .streams import binance_stream_generator


@dataclass
class Binance(Exchange):
    name: str = "binance"

    @staticmethod
    async def book_ticker_stream(symbol: str) -> AsyncIterator[dict]:
        async for book in binance_stream_generator(symbol, "@bookTicker"):
            if book:
                yield book
