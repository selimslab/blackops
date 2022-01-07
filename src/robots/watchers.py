import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Optional, Tuple

import src.pubsub.pub as pub
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.streams.factory import stream_factory
from src.monitoring import logger


@dataclass
class BookWatcher:
    pubsub_key: str
    stream: AsyncGenerator
    exchange: Optional[ExchangeAPIClientBase] = None
    last_updated = datetime.now()
    quote: Optional[Decimal] = None
    books_seen: int = 0

    async def clear_quote(self):
        await asyncio.sleep(0.2)
        self.quote = None

    async def watch_books(self):
        if not self.stream:
            raise ValueError("No stream")
        if not self.exchange:
            raise ValueError("No exchange")

        async for book in self.stream:
            new_quote = self.exchange.get_mid(book)
            self.quote = new_quote
            self.last_updated = datetime.now()
            asyncio.create_task(self.clear_quote())
            await asyncio.sleep(0)


@dataclass
class BalanceWatcher:
    pubsub_key: str
    exchange: ExchangeAPIClientBase
    balances: Optional[dict] = None
    last_updated = datetime.now()

    async def watch_balance(self):
        res = await self.exchange.get_account_balance()
        self.balances = res
        self.last_updated = datetime.now()


@dataclass
class WatcherFactory:

    BOOK_WATCHERS: Dict[str, BookWatcher] = field(default_factory=dict)
    BALANCE_WATCHERS: Dict[str, BalanceWatcher] = field(default_factory=dict)

    def create_book_watcher_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str, pub_channel: str
    ) -> Tuple:

        key = "_".join((ex_type.value, network.value, "book"))
        if key in self.BOOK_WATCHERS:
            logger.info(f"Reusing book watcher for {ex_type}")
            return key, self.BOOK_WATCHERS[key]

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        stream = stream_factory.create_stream_if_not_exists(
            ex_type, symbol, pub_channel
        )

        watcher = BookWatcher(pubsub_key=key, exchange=api_client, stream=stream)

        self.BOOK_WATCHERS[key] = watcher

        return key, watcher

    def create_balance_watcher_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType
    ) -> Tuple:
        key = "_".join((ex_type.value, network.value, "balance"))

        if key in self.BALANCE_WATCHERS:
            logger.info(f"Reusing balance watcher for {ex_type}")
            return key, self.BALANCE_WATCHERS[key]

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        watcher = BalanceWatcher(pubsub_key=key, exchange=api_client)

        self.BALANCE_WATCHERS[key] = watcher

        return key, watcher


watcher_factory = WatcherFactory()
