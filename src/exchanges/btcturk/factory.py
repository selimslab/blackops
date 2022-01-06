from src.environment import apiKey, apiSecret

from .real.main import BtcturkApiClient
from .testnet.testnet import BtcturkApiClientTestnet


def create_real_client():
    return BtcturkApiClient(api_key=apiKey, api_secret=apiSecret)


def create_testnet_client():
    return BtcturkApiClientTestnet()


btc_real_api_client_public = BtcturkApiClient()
