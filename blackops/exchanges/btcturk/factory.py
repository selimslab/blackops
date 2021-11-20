from .base import BtcturkBase
from .real import btcturk_api_client_real
from .testnet import BtcturkTestnetApiClient


def create_real_client():
    return BtcturkBase(api_client=btcturk_api_client_real, name="btcturk_real")


def create_testnet_client():
    return BtcturkBase(api_client=BtcturkTestnetApiClient(), name="btcturk_testnet")
