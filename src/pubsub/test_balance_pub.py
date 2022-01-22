from dataclasses import dataclass

from src.domain import OrderType, create_asset_pair
from src.domain.models import AssetPair, AssetPairSymbol
from src.exchanges.factory import ExchangeType, NetworkType
from src.pubsub.factory import pub_factory


@dataclass
class A:
    pair: AssetPair

    def __post_init__(self) -> None:

        self.b = B(self.pair)


@dataclass
class B:
    pair: AssetPair

    def go(self):
        self.pair.base.free += 100


def test_balances():
    bp = pub_factory.create_balance_pub_if_not_exists(
        ex_type=ExchangeType.BTCTURK, network=NetworkType.TESTNET
    )
    pair = create_asset_pair(base="USDT", quote="TRY")

    a = A(pair)

    bp.add_pair(pair)

    a.b.go()

    print(bp.get_updated_pair(pair))


if __name__ == "__main__":
    test_balances()
