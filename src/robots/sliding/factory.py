from src.domain import Asset
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.monitoring import logger
from src.robots.pubs import pub_factory
from src.robots.sliding.main import SlidingWindowTrader
from src.stgs.sliding import SlidingWindowConfig
from src.streams.factory import stream_factory


def sliding_window_factory(config: SlidingWindowConfig):

    config.is_valid()

    stg = config.input
    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL

    balance_watcher = pub_factory.create_balance_pub_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network
    )

    bridge_station = None
    if stg.bridge:
        bridge_station = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote,
        )

    pair = config.create_pair()

    if stg.bridge:

        leader_watcher = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.base + stg.quote,
        )

    else:
        leader_watcher = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=pair.symbol,
        )

    follower_watcher = pub_factory.create_book_pub_if_not_exists(
        ex_type=ExchangeType(stg.bridge_exchange), network=network, symbol=pair.symbol
    )

    if network == NetworkType.TESTNET:
        follower_watcher.api_client.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), stg.max_step * stg.quote_step_qty * 2
        )

    trader = SlidingWindowTrader(
        config=config,
        leader_station=leader_watcher,
        follower_station=follower_watcher,
        bridge_station=bridge_station,
        balance_station=balance_watcher,
    )
    return trader
