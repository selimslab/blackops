import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Optional, Tuple, Union

import src.pubsub.pub as pub
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.streams.factory import stream_factory
from src.monitoring import logger



@dataclass
class BalanceWatcher:
    pubsub_key: str
    exchange: ExchangeAPIClientBase
    balances: Optional[dict] = None
    last_updated = datetime.now()

    async def watch_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            self.balances = res
            self.last_updated = datetime.now()


@dataclass
class BookWatcher:
    pubsub_key: str
    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase

    book: Optional[Union[str, dict]] = None
    books_seen: int = 0
    last_updated = datetime.now()

    async def watch_books(self):
        if not self.stream:
            raise ValueError("No stream")
        if not self.api_client:
            raise ValueError("No api_client")

        async for book in self.stream:
            # new_quote = self.exchange.get_mid(book)
            self.book = book
            self.last_updated = datetime.now()
            await asyncio.sleep(0)


@dataclass
class WatcherFactory:

    BOOK_WATCHERS: Dict[str, BookWatcher] = field(default_factory=dict)
    BALANCE_WATCHERS: Dict[str, BalanceWatcher] = field(default_factory=dict)

    def create_book_watcher_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> BookWatcher:

        key = "_".join((ex_type.value, network.value, "book"))
        if key in self.BOOK_WATCHERS:
            logger.info(f"Reusing book watcher for {ex_type}")
            return self.BOOK_WATCHERS[key]

        stream = stream_factory.create_stream_if_not_exists(
            ex_type, symbol
        )

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        watcher = BookWatcher(pubsub_key=key, api_client=api_client, stream=stream)

        self.BOOK_WATCHERS[key] = watcher

        return watcher

    def create_balance_watcher_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType
    ) -> BalanceWatcher:
        key = "_".join((ex_type.value, network.value, "balance"))

        if key in self.BALANCE_WATCHERS:
            logger.info(f"Reusing balance watcher for {ex_type}")
            return self.BALANCE_WATCHERS[key]

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        watcher = BalanceWatcher(pubsub_key=key, exchange=api_client)

        self.BALANCE_WATCHERS[key] = watcher

        return watcher


watcher_factory = WatcherFactory()
