from .base import BtcturkBase


def create_real_client(api_client):
    return BtcturkBase(api_client=api_client, name="btcturk_real")


def create_testnet_client(api_client):
    return BtcturkBase(api_client=api_client, name="btcturk_testnet")
