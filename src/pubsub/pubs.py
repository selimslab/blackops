import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, Union

from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.monitoring import logger
from src.periodic import periodic
from src.streams.factory import stream_factory


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

    async def run(self):
        await periodic(
            self.ask_balance,
            sleep_seconds.update_balances,
        )

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


@dataclass
class PubFactory:

    PUBS: Dict[str, PubsubProducer] = field(default_factory=dict)

    def remove_pub(self, pubsub_key: str):
        if pubsub_key in self.PUBS:
            del self.PUBS[pubsub_key]  # type: ignore
            stream_factory.remove_stream(pubsub_key)

    def create_book_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> BookPub:

        pubsub_key = "_".join((ex_type.value, network.value, symbol))
        if pubsub_key in self.PUBS:
            return self.PUBS[pubsub_key]  # type: ignore

        stream = stream_factory.create_stream_if_not_exists(ex_type, symbol, pubsub_key)

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        pub = BookPub(pubsub_key=pubsub_key, api_client=api_client, stream=stream)

        self.PUBS[pubsub_key] = pub

        return pub

    def create_balance_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType
    ) -> BalancePub:
        pubsub_key = "_".join((ex_type.value, network.value, "balance"))

        if pubsub_key in self.PUBS:
            return self.PUBS[pubsub_key]  # type: ignore

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        pub = BalancePub(pubsub_key=pubsub_key, exchange=api_client)

        self.PUBS[pubsub_key] = pub

        return pub


pub_factory = PubFactory()
