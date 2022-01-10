from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from pydantic.main import BaseModel

AssetSymbol = str
AssetPairSymbol = str

BPS = Decimal("1") / Decimal("10000")
taker_fee_bps: Decimal = Decimal("12")
maker_fee_bps: Decimal = taker_fee_bps / 2


class Asset(BaseModel):
    symbol: AssetSymbol
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    def __str__(self) -> str:
        return f"{self.symbol}"

    @property
    def total_balance(self):
        return self.free + self.locked


@dataclass
class AssetPair:
    base: Asset
    quote: Asset

    def __post_init__(self):
        self.symbol: AssetPairSymbol = self.base.symbol + self.quote.symbol

    def __str__(self):
        return f"{self.base}_{self.quote}"


OrderId = int


class OrderType(str, Enum):
    BUY = "buy"
    SELL = "sell"
