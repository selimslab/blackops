from dataclasses import dataclass

from blackops.domain.models import Asset, AssetPair, Exchange, Trader


@dataclass
class AlgoTrader(Trader):

    ...

    # pubsub
    #
