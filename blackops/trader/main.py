from dataclasses import dataclass

from blackops.domain.models import (
    Asset,
    AssetPair,
    Exchange,
    LeaderFollowerStrategy,
    Trader,
)


@dataclass
class DummyTrader(Trader):
    ...


@dataclass
class RealTrader(Trader):

    ...
