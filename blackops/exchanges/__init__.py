from typing import Union

from .binance.base import BinanceBase
from .btcturk.real import BtcturkApiClient
from .btcturk.testnet import BtcturkApiClientTestnet

LEADERS = BinanceBase
FOLLOWERS = Union[BtcturkApiClient, BtcturkApiClientTestnet]

EXCHANGE = Union[LEADERS, FOLLOWERS]
