from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

import blackops.exchanges.binance.factory as binance_factory
import blackops.exchanges.btcturk.factory as btcturk_factory
from blackops.exchanges.base import ExchangeAPIClientBase
from blackops.util.logger import logger


class ExchangeType(str, Enum):
    BINANCE = "binance"
    BTCTURK = "btcturk"


class NetworkType(str, Enum):
    TESTNET = "testnet"
    REAL = "real"


@dataclass
class ApiClientFactory:

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

    API_CLIENTS: Dict[tuple, ExchangeAPIClientBase] = field(default_factory=dict)

    def create_api_client_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType
    ) -> ExchangeAPIClientBase:
        key = (ex_type, network)
        if key in self.API_CLIENTS:
            logger.info(f"reusing api client for {(ex_type, network)}")
            return self.API_CLIENTS[key]

        factory_func = self.API_CLIENT_FACTORIES.get(ex_type, {}).get(network)  # type: ignore

        if not factory_func:
            raise ValueError(f"unknown exchange: {ex_type}")

        client = factory_func()
        self.API_CLIENTS[key] = client

        return client


api_client_factory = ApiClientFactory()
