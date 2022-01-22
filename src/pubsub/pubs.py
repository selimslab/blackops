import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Optional, Union

from src.domain.models import AssetPair, AssetPairSymbol
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import periodic


@dataclass
class PublisherBase:
    pubsub_key: str

    async def run(self):
        pass


@dataclass
class BalancePub(PublisherBase):
    exchange: ExchangeAPIClientBase
    last_updated = datetime.now()
    balances: Optional[dict] = None
    pairs: Dict[AssetPairSymbol, AssetPair] = field(default_factory=dict)

    async def run(self):
        await periodic(
            self.ask_balance,
            sleep_seconds.update_balances,
        )

    async def ask_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            self.update_balances(res)
            self.last_updated = datetime.now()

    def add_pair(self, pair: AssetPair):
        self.pairs[pair.symbol] = pair

    def update_balances(self, res: dict) -> None:
        for pair in self.pairs.values():
            balances = self.exchange.parse_account_balance(
                res, symbols=[pair.base.symbol, pair.quote.symbol]
            )
            base_balances: dict = balances[pair.base.symbol]
            pair.base.free = Decimal(base_balances["free"])
            pair.base.locked = Decimal(base_balances["locked"])

            quote_balances: dict = balances[pair.quote.symbol]
            pair.quote.free = Decimal(quote_balances["free"])
            pair.quote.locked = Decimal(quote_balances["locked"])


@dataclass
class BookPub(PublisherBase):
    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase

    book: Optional[Union[str, dict]] = None
    books_seen: int = 0
    last_updated = datetime.now()

    async def run(self):
        await self.consume_stream()

    async def consume_stream(self):
        if not self.stream:
            raise ValueError("No stream")
        if not self.api_client:
            raise ValueError("No api_client")

        async for book in self.stream:
            # new_quote = self.exchange.get_mid(book)
            self.book = book
            self.last_updated = datetime.now()
            self.books_seen += 1
            await asyncio.sleep(0)


PubsubProducer = Union[BalancePub, BookPub]
