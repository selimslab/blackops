from typing import Tuple

from src.domain import Asset
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.stgs.sliding import SlidingWindowConfig
from src.robots.sliding.main import SlidingWindowTrader
from src.robots.watchers import BalanceWatcher, watcher_factory
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



def sliding_window_factory(config: SlidingWindowConfig):

    config.is_valid()

    leader_api_client, follower_api_client = create_clients(config)

    stg = config.input
    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL            

    balance_watcher = watcher_factory.create_balance_watcher_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network
    )
    
    if stg.bridge:
        bridge_watcher = watcher_factory.create_book_watcher_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote
        )

    pair = config.create_pair()

    if stg.bridge:

        leader_watcher = watcher_factory.create_book_watcher_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.base + stg.quote
        )

    else:
        leader_watcher = watcher_factory.create_book_watcher_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=pair.symbol
        )


    follower_watcher = watcher_factory.create_book_watcher_if_not_exists(
        ex_type=ExchangeType(stg.bridge_exchange),
        network=network,
        symbol=pair.symbol
    )

    trader = SlidingWindowTrader(
        config=config,
        leader_station=leader_watcher,
        follower_station=follower_watcher,
        bridge_station=bridge_watcher,
        balance_station=balance_watcher
    )
    return trader
