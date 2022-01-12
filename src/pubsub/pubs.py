import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, Union

import src.pubsub.log_pub as log_pub
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.monitoring import logger
from src.streams.factory import stream_factory


@dataclass
class PublisherBase:
    pubsub_key: str


@dataclass
class StatsPub(PublisherBase):
    pass


stats_pub = StatsPub(pubsub_key=log_pub.DEFAULT_CHANNEL)


@dataclass
class BalancePub(PublisherBase):
    exchange: ExchangeAPIClientBase
    last_updated = datetime.now()
    balances: Optional[dict] = None

    async def ask_balance(self):
        res = await self.exchange.get_account_balance()
        if res:
            self.balances = res
            self.last_updated = datetime.now()


@dataclass
class BookPub(PublisherBase):

    stream: AsyncGenerator
    api_client: ExchangeAPIClientBase

    book: Optional[Union[str, dict]] = None
    books_seen: int = 0
    last_updated = datetime.now()

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


@dataclass
class PubFactory:

    PUBS: Dict[str, PubsubProducer] = field(default_factory=dict)

    def create_book_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> BookPub:

        key = "_".join((ex_type.value, network.value, symbol))
        if key in self.PUBS:
            logger.info(f"Reusing book watcher for {ex_type}")
            return self.PUBS[key]  # type: ignore

        stream = stream_factory.create_stream_if_not_exists(ex_type, symbol)

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        watcher = BookPub(pubsub_key=key, api_client=api_client, stream=stream)

        self.PUBS[key] = watcher

        return watcher

    def create_balance_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType
    ) -> BalancePub:
        key = "_".join((ex_type.value, network.value, "balance"))

        if key in self.PUBS:
            logger.info(f"Reusing balance watcher for {ex_type}")
            return self.PUBS[key]  # type: ignore

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        watcher = BalancePub(pubsub_key=key, exchange=api_client)

        self.PUBS[key] = watcher

        return watcher


pub_factory = PubFactory()
