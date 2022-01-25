from src.domain import Asset
from src.domain.models import create_asset_pair
from src.exchanges.factory import ExchangeType, NetworkType
from src.monitoring import logger
from src.pubsub import pub_factory

from .config import LeaderFollowerConfig
from .main import LeaderFollowerTrader


def sliding_window_factory(config: LeaderFollowerConfig):

    config.is_valid()

    stg = config.input
    network = NetworkType.TESTNET if config.testnet else NetworkType.REAL

    balance_pub = pub_factory.create_balance_pub_if_not_exists(
        ex_type=ExchangeType(config.follower_exchange), network=network
    )

    pair = create_asset_pair(stg.base, stg.quote)

    follower_pub = pub_factory.create_book_pub_if_not_exists(
        ex_type=ExchangeType(config.follower_exchange),
        network=network,
        symbol=pair.symbol,  # eth try
    )
    if network == NetworkType.TESTNET:
        follower_pub.api_client.dummy_exchange.add_balance(  # type:ignore
            Asset(symbol=stg.quote), config.max_step * config.quote_step_qty * 2
        )

    bridge_pub = None
    if stg.bridge:
        leader_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(config.leader_exchange),
            network=network,
            symbol=stg.base + stg.bridge,  # btc usd
        )

        bridge_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(config.bridge_exchange),
            network=network,
            symbol=stg.bridge + stg.quote,  # usd try
        )
    else:
        leader_pub = pub_factory.create_book_pub_if_not_exists(
            ex_type=ExchangeType(config.leader_exchange),
            network=network,
            symbol=pair.symbol,
        )

    trader = LeaderFollowerTrader(
        config=config,
        leader_pub=leader_pub,
        follower_pub=follower_pub,
        bridge_pub=bridge_pub,
        balance_pub=balance_pub,
    )
    return trader
