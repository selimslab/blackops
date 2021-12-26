from enum import Enum

import blackops.exchanges.binance.factory as binance_factory
import blackops.exchanges.btcturk.factory as btcturk_factory
from blackops.exchanges.base import ExchangeBase


class ExchangeType(str, Enum):
    BINANCE = "binance"
    BTCTURK = "btcturk"


class NetworkType(str, Enum):
    TESTNET = "testnet"
    REAL = "real"


API_CLIENT_FACTORIES = {
    ExchangeType.BINANCE: {
        NetworkType.TESTNET: lambda: binance_factory.create_testnet_client(),
        NetworkType.REAL: lambda: binance_factory.create_real_client(),
    },
    ExchangeType.BTCTURK: {
        NetworkType.TESTNET: lambda: btcturk_factory.create_testnet_client(),
        NetworkType.REAL: lambda: btcturk_factory.create_real_client(),
    },
}


def create_api_client(ex_type: ExchangeType, network: NetworkType) -> ExchangeBase:
    factory_func = API_CLIENT_FACTORIES.get(ex_type, {}).get(network)  # type: ignore

    if not factory_func:
        raise ValueError(f"unknown exchange: {ex_type}")

    return factory_func()
