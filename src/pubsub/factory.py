from dataclasses import dataclass, field
from typing import Dict

import src.streams.bn as bn_streams
import src.streams.btcturk as btc_streams
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory

from .pubs import BalancePub, BinancePub, BookPub, PubsubProducer


@dataclass
class PubFactory:

    PUBS: Dict[str, PubsubProducer] = field(default_factory=dict)

    def remove_pub(self, pubsub_key: str):
        if pubsub_key in self.PUBS:
            del self.PUBS[pubsub_key]  # type: ignore

    def create_binance_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> BinancePub:

        pubsub_key = "_".join((ex_type.value, network.value, symbol))
        if pubsub_key in self.PUBS:
            return self.PUBS[pubsub_key]  # type: ignore

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        stream = bn_streams.create_book_stream(symbol)
        pub = BinancePub(pubsub_key=pubsub_key, api_client=api_client, stream=stream)

        self.PUBS[pubsub_key] = pub

        return pub

    def create_bt_pub_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> BookPub:

        pubsub_key = "_".join((ex_type.value, network.value, symbol))
        if pubsub_key in self.PUBS:
            return self.PUBS[pubsub_key]  # type: ignore

        api_client = api_client_factory.create_api_client_if_not_exists(
            ex_type, network
        )

        stream = btc_streams.create_book_stream(symbol)
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
