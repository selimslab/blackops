from blackops.environment import apiKey, apiSecret

from .real import BtcturkApiClient
from .testnet import BtcturkApiClientTestnet


def create_real_client():
    return BtcturkApiClient(api_key=apiKey, api_secret=apiSecret)


def create_testnet_client():
    return BtcturkApiClientTestnet()
