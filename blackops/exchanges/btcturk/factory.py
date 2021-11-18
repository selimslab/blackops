from .api_clients.real import btcturk_api_client_real
from .api_clients.testnet import create_btcturk_api_client_testnet
from .exchanges.real import BtcturkReal
from .exchanges.testnet import BtcturkTestnet


def create_testnet_client(balances):
    btcturk_client_testnet = BtcturkTestnet(
        api_client=create_btcturk_api_client_testnet(balances)
    )
    return btcturk_client_testnet


btcturk_client_real = BtcturkReal(api_client=btcturk_api_client_real)
