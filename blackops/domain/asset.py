from dataclasses import dataclass
from decimal import Decimal

from pydantic.main import BaseModel

AssetSymbol = str
AssetPairSymbol = str


class Asset(BaseModel):
    symbol: AssetSymbol
    balance: Decimal = Decimal("0")
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    def __str__(self):
        return f"{self.symbol}"


@dataclass
class AssetPair:
    base: Asset
    quote: Asset

    def __post_init__(self):
        self.symbol: AssetPairSymbol = self.base.symbol + self.quote.symbol

    def __str__(self):
        return f"{self.base}_{self.quote}"
