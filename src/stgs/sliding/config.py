from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain import BPS
from src.exchanges.factory import ExchangeType
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import LeaderFollowerInput


class UnitSignalBPS(BaseModel):
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)
    step: Decimal = Decimal(0)
    slope_risk: Decimal = Decimal(0)


class LeaderFollowerConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge: str = Field("USDT")
    bridge_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    testnet = False

    min_sell_qty: Decimal = Decimal(400)
    min_buy_qty: Decimal = Decimal(2000)
    max_spread_bps: Decimal = Decimal(15)

    sell_step: Decimal = Decimal(2)

    max_step: Decimal = Decimal(20)
    quote_step_qty: Decimal = Decimal(4000)

    unit_signal_bps: UnitSignalBPS = UnitSignalBPS(
        buy=Decimal(15) * BPS,
        sell=Decimal(5) * BPS,
        step=Decimal(1) * BPS,
        slope_risk=Decimal(9) * BPS,
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
