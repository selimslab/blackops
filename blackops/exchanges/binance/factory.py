from .base import BinanceBase


def create_real_client():
    return BinanceBase(name="binance_real")


def create_testnet_client():
    return BinanceBase(name="binance_testnet")
