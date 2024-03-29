from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict

from pydantic.main import BaseModel

DECIMAL_2 = Decimal(2)

AssetSymbol = str
AssetPairSymbol = str

BPS = Decimal("1") / Decimal("10000")
taker_fee_bps: Decimal = Decimal("8")
maker_fee_bps: Decimal = taker_fee_bps / 2


@dataclass
class Book:
    ask: Decimal = Decimal(0)
    mid: Decimal = Decimal(0)
    bid: Decimal = Decimal(0)
    spread_bps: Decimal = Decimal(0)
    seen: int = 0
    processed: int = 0


class Asset(BaseModel):
    symbol: AssetSymbol
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    def __str__(self) -> str:
        return f"{self.symbol}"

    @property
    def total_balance(self):
        return self.free + self.locked


class AssetPair(BaseModel):
    base: Asset
    quote: Asset

    @property
    def symbol(self):
        return self.base.symbol + self.quote.symbol

    def __str__(self):
        return f"{self.base}_{self.quote}"


@dataclass
class AssetFactory:
    assets: Dict[AssetSymbol, Asset] = field(default_factory=dict)

    def create_asset(self, symbol: AssetSymbol) -> Asset:
        if symbol not in self.assets:
            self.assets[symbol] = Asset(symbol=symbol)
        return self.assets[symbol]


asset_factory = AssetFactory()


def create_asset_pair(base: AssetSymbol, quote: AssetSymbol) -> AssetPair:
    return AssetPair(
        base=asset_factory.create_asset(base), quote=asset_factory.create_asset(quote)
    )


OrderId = int


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
