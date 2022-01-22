from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict

from pydantic.main import BaseModel

AssetSymbol = str
AssetPairSymbol = str

BPS = Decimal("1") / Decimal("10000")
taker_fee_bps: Decimal = Decimal("8")
maker_fee_bps: Decimal = taker_fee_bps / 2


class Asset(BaseModel):
    symbol: AssetSymbol
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    @property
    def total_balance(self):
        return self.free + self.locked


class AssetPair(BaseModel):
    base: Asset
    quote: Asset

    @property
    def symbol(self):
        return self.base.symbol + self.quote.symbol


@dataclass
class AssetFactory:
    assets: Dict[AssetSymbol, Asset] = field(default_factory=dict)

    def create_asset(self, symbol: AssetSymbol) -> Asset:
        if symbol not in self.assets:
            self.assets[symbol] = Asset(symbol=symbol)
        return self.assets[symbol]

    def create_asset_pair(self, base: AssetSymbol, quote: AssetSymbol) -> AssetPair:
        return AssetPair(base=self.create_asset(base), quote=self.create_asset(quote))


asset_factory = AssetFactory()


def create_asset_pair(base: AssetSymbol, quote: AssetSymbol) -> AssetPair:
    return AssetPair(base=Asset(symbol=base), quote=Asset(symbol=quote))


OrderId = int


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
