from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain import BPS
from src.exchanges.factory import ExchangeType
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import LeaderFollowerInput


class UnitSignalBPS(BaseModel):
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)
    hold: Decimal = Decimal(0)


class LeaderFollowerConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge: str = Field("USDT")
    bridge_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    max_step: Decimal = Decimal(8)
    quote_step_qty: Decimal = Decimal(10000)

    min_sell_qty: Decimal = Decimal(400)
    min_buy_qty: Decimal = Decimal(4000)

    testnet = False

    unit_signal_bps: UnitSignalBPS = UnitSignalBPS(
        sell=Decimal(2) * BPS, hold=Decimal("0.7") * BPS, buy=Decimal(30) * BPS
    )

    input: LeaderFollowerInput

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        # sha = dict_to_hash(self.input.dict())[:7]
        mode = "test" if self.input.testnet else "real"
        self.sha = f"{self.input.base}_{self.input.quote}_{mode}"

    def is_valid(self):
        return self.input.is_valid()
