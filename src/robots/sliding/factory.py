from src.domain import Asset
from src.domain.models import create_asset_pair
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.factory import ExchangeType, NetworkType, api_client_factory
from src.monitoring import logger
from src.pubsub.pubs import pub_factory
from src.robots.sliding.main import SlidingWindowTrader
from src.stgs.sliding import SlidingWindowConfig
from src.streams.factory import stream_factory


def sliding_window_factory(config: SlidingWindowConfig):

    config.is_valid()

    stg = config.input
    network = NetworkType.TESTNET if stg.testnet else NetworkType.REAL

    balance_pub = pub_factory.create_balance_pub_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network
    )

    bridge_pub = None
    if stg.bridge:
        bridge_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote,
        )

    pair = create_asset_pair(stg.base, stg.quote)

    follower_pub = pub_factory.create_book_pub_if_not_exists(
        ex_type=ExchangeType(stg.follower_exchange), network=network, symbol=pair.symbol
    )

    if network == NetworkType.TESTNET:
        follower_pub.api_client.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), stg.max_step * stg.quote_step_qty * 2
        )

    if stg.bridge:
        leader_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.leader_exchange),
            network=network,
            symbol=stg.base + stg.quote,
        )

    else:
        leader_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(stg.leader_exchange),
            network=network,
            symbol=pair.symbol,
        )

    trader = SlidingWindowTrader(
        config=config,
        leader_pub=leader_pub,
        follower_pub=follower_pub,
        bridge_pub=bridge_pub,
        balance_pub=balance_pub,
    )
    return trader
