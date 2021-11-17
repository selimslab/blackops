from .real import BtcturkReal
from .real_api import btcturk_api_client_real
from .testnet import BtcturkTestnet
from .testnet_api import btcturk_api_client_testnet


def create_btcturk_client(testnet=True):
    if testnet is True:
        return BtcturkTestnet(api_client=btcturk_api_client_testnet)
    else:
        return BtcturkReal(api_client=btcturk_api_client_real)


btcturk_client_testnet = create_btcturk_client()

btcturk_client_real = create_btcturk_client(testnet=False)
