from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Asset:
    symbol: str
    balance: Decimal = Decimal(0)

    def __str__(self):
        return f"{self.symbol} {self.balance}"


@dataclass
class AssetPair:
    base: Asset
    quote: Asset

    def __post_init__(self):
        self.symbol = self.base.symbol + self.quote.symbol
        self.bt_order_symbol = self.base.symbol + "_" + self.quote.symbol

    def __str__(self):
        return f"{self.base}, {self.quote}"
