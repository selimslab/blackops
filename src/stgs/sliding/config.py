from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


from src.numbers import round_decimal
from src.idgen import dict_to_hash
from .inputs import SlidingWindowInput

from src.stgs.base import StrategyType, StrategyConfigBase
from src.stgs import Asset, AssetPair, maker_fee_bps, taker_fee_bps


class SleepSeconds(BaseModel):
    update_balances: float = 0.72
    cancel_all_open_orders: float = 2
    broadcast_stats: float = 2

class SlidingWindowConfig(StrategyConfigBase):
    input:SlidingWindowInput

    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    reference_price:Decimal

    base_step_qty: Decimal = Decimal(0)

    maker_credit_bps: Decimal = Decimal(0)

    taker_credit_bps: Decimal = Decimal(0)

    sleep_seconds: SleepSeconds = Field(default_factory=SleepSeconds)

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        sha = dict_to_hash(self.input.dict())[:7]
        self.sha = sha

        self.set_params(self.reference_price)

    def set_params(self, ticker):
        self.reference_price = ticker

        self.maker_credit_bps = 2 * maker_fee_bps + self.input.margin_bps
        self.taker_credit_bps = 2 * taker_fee_bps + self.input.margin_bps

        self.base_step_qty = round_decimal(self.input.quote_step_qty / ticker)
        

    def is_valid(self):
        return self.input.is_valid()

    def create_pair(self)->AssetPair:
        return AssetPair(
            Asset(symbol=self.input.base), Asset(symbol=self.input.quote)
        )