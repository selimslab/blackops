from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.domain import (
    BPS,
    Asset,
    AssetPair,
    create_asset_pair,
    maker_fee_bps,
    taker_fee_bps,
)
from src.idgen import dict_to_hash
from src.numberops import round_decimal
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import SlidingWindowInput


class SleepSeconds(BaseModel):
    update_balances: float = 0.72
    cancel_all_open_orders: float = 1.2
    broadcast_stats: float = 0.4
    clear_prices: float = 0.4


class Credits(BaseModel):
    maker: Decimal = Decimal(0)
    taker: Decimal = Decimal(0)
    step: Decimal = Decimal(0)


class SlidingWindowConfig(StrategyConfigBase):
    input: SlidingWindowInput

    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    reference_price: Decimal = Decimal(0)

    pair: Optional[AssetPair]

    base_step_qty: Decimal = Decimal(0)

    credits: Credits = Credits()

    sleep_seconds: SleepSeconds = Field(default_factory=SleepSeconds)

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        sha = dict_to_hash(self.input.dict())[:7]
        self.sha = sha

        self.pair = create_asset_pair(self.input.base, self.input.quote)

        self.credits.maker = (2 * maker_fee_bps + self.input.margin_bps) * BPS
        self.credits.taker = (2 * taker_fee_bps + self.input.margin_bps) * BPS
        self.credits.step = self.input.step_bps * BPS

        self.set_ticker_params()

    def set_ticker_params(self):
        self.base_step_qty = round_decimal(
            self.input.quote_step_qty / self.reference_price
        )

    def is_valid(self):

        return self.input.is_valid()
