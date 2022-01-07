from typing import Tuple

from src.domain import Asset, AssetPair
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.stgs.sliding import SlidingWindowConfig
from src.robots.sliding.main import SlidingWindowTrader
from src.robots.watchers import watcher_factory
from src.streams.factory import stream_factory
from src.monitoring import logger


def create_clients(config: SlidingWindowConfig):

    stg = config.input

    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL

    follower_api_client: ExchangeAPIClientBase = (
        api_client_factory.create_api_client_if_not_exists(
            ExchangeType(stg.follower_exchange), network
        )
    )

    if network == NetworkType.TESTNET and follower_api_client:
        follower_api_client.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), stg.max_step * stg.quote_step_qty * 2
        )

    leader_api_client: ExchangeAPIClientBase = (
        api_client_factory.create_api_client_if_not_exists(
            ExchangeType(stg.leader_exchange), network
        )
    )

    return leader_api_client, follower_api_client


def create_balance_watcher_from_strategy(config: SlidingWindowConfig) -> Tuple:

    stg = config.input

    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL
    (
        balance_pubsub_key,
        balance_watcher,
    ) = watcher_factory.create_balance_watcher_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network
    )
    return balance_pubsub_key, balance_watcher


def create_bridge_watcher_from_strategy(config: SlidingWindowConfig) -> Tuple:
    bridge_pubsub_key = None
    bridge_watcher = None

    stg = config.input

    if stg.bridge:
        network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL
        (
            bridge_pubsub_key,
            bridge_watcher,
        ) = watcher_factory.create_book_watcher_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote
        )
    return bridge_pubsub_key, bridge_watcher


def sliding_window_factory(config: SlidingWindowConfig):

    config.is_valid()

    leader_api_client, follower_api_client = create_clients(config)

    balance_pubsub_key, balance_watcher = create_balance_watcher_from_strategy(config)
    bridge_pubsub_key, bridge_watcher = create_bridge_watcher_from_strategy(config)

    stg = config.input

    pair = config.create_pair()

    if stg.bridge:
        leader_book_stream = stream_factory.create_stream_if_not_exists(
            ExchangeType(stg.leader_exchange), stg.base + stg.bridge
        )
    else:
        leader_book_stream = stream_factory.create_stream_if_not_exists(
            ExchangeType(stg.leader_exchange), pair.symbol
        )

    follower_book_stream = stream_factory.create_stream_if_not_exists(
        ExchangeType(stg.follower_exchange), pair.symbol
    )

    trader = SlidingWindowTrader(
        config=config,
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
