from typing import Tuple

from pydantic import networks

from src.domain.asset import Asset, AssetPair
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.robots.config import SlidingWindowConfig
from src.robots.sliding.main import SlidingWindowTrader
from src.robots.watchers import BalanceWatcher, BookWatcher, watcher_factory
from src.streams.factory import stream_factory
from src.monitoring import logger


def create_clients(stg: SlidingWindowConfig):

    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL

    follower_api_client: ExchangeAPIClientBase = (
        api_client_factory.create_api_client_if_not_exists(
            ExchangeType(stg.follower_exchange), network
        )
    )

    if network == NetworkType.TESTNET and follower_api_client:
        follower_api_client.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), stg.max_usable_quote_amount_y * 2
        )

    leader_api_client: ExchangeAPIClientBase = (
        api_client_factory.create_api_client_if_not_exists(
            ExchangeType(stg.leader_exchange), network
        )
    )

    return leader_api_client, follower_api_client


def create_balance_watcher_from_strategy(stg: SlidingWindowConfig) -> Tuple:
    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL
    (
        balance_pubsub_key,
        balance_watcher,
    ) = watcher_factory.create_balance_watcher_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network
    )
    return balance_pubsub_key, balance_watcher


def create_bridge_watcher_from_strategy(stg: SlidingWindowConfig) -> Tuple:
    bridge_pubsub_key = None
    bridge_watcher = None

    if stg.bridge:
        network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL
        (
            bridge_pubsub_key,
            bridge_watcher,
        ) = watcher_factory.create_book_watcher_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote,
            pub_channel=stg.sha,
        )
    return bridge_pubsub_key, bridge_watcher


def validate(stg: SlidingWindowConfig):
    if not isinstance(stg, SlidingWindowConfig):
        raise ValueError(f"wrong strategy type: {stg.type}")

    if not stg.sha:
        raise ValueError(f"sha is not set: {stg}")

    stg.is_valid()


def sliding_window_factory(stg: SlidingWindowConfig):

    validate(stg)

    pub_channel = stg.sha

    leader_api_client, follower_api_client = create_clients(stg)

    balance_pubsub_key, balance_watcher = create_balance_watcher_from_strategy(stg)
    bridge_pubsub_key, bridge_watcher = create_bridge_watcher_from_strategy(stg)

    pair = AssetPair(Asset(symbol=stg.base), Asset(symbol=stg.quote))

    if stg.bridge:
        leader_book_stream = stream_factory.create_stream_if_not_exists(
            ExchangeType(stg.leader_exchange), stg.base + stg.bridge, pub_channel
        )
    else:
        leader_book_stream = stream_factory.create_stream_if_not_exists(
            ExchangeType(stg.leader_exchange), pair.symbol, pub_channel
        )

    follower_book_stream = stream_factory.create_stream_if_not_exists(
        ExchangeType(stg.follower_exchange), pair.symbol, pub_channel
    )

    trader = SlidingWindowTrader(
        config=stg,
        leader_api_client=leader_api_client,
        follower_api_client=follower_api_client,
        leader_book_stream=leader_book_stream,
        follower_book_stream=follower_book_stream,
        bridge_watcher=bridge_watcher,
        balance_watcher=balance_watcher,
        balance_pubsub_key=balance_pubsub_key,
        bridge_pubsub_key=bridge_pubsub_key,
    )
    return trader, balance_watcher, bridge_watcher
