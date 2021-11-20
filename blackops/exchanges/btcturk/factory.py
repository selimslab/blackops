from .base import BtcturkBase
from .real import btcturk_api_client_real
from .testnet import BtcturkTestnetApiClient


def create_real_client(api_client):
    return BtcturkBase(api_client=api_client, name="btcturk_real")


def create_testnet_client(api_client):
    return BtcturkBase(api_client=api_client, name="btcturk_testnet")
