from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.exchanges.factory import ExchangeType
from src.idgen import dict_to_hash
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import SlidingWindowInput


class SlidingWindowConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge_exchange: Optional[ExchangeType] = ExchangeType.BTCTURK

    max_step: Decimal = Decimal(8)

    quote_step_qty: Decimal = Decimal(7200)

    margin_bps: Decimal = Decimal("2")

    sell_to_buy_ratio: Decimal = Decimal("1.6")

    minimum_sell_qty: Decimal = Decimal("200")

    input: SlidingWindowInput

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        # sha = dict_to_hash(self.input.dict())[:7]
        mode = "test" if self.input.testnet else "real"
        self.sha = f"{self.input.base}{self.input.quote}_{mode}"

    def is_valid_exchanges(self):
        if self.leader_exchange != ExchangeType.BINANCE:
            raise ValueError(f"{self.leader_exchange} is not supported")

        if self.follower_exchange != ExchangeType.BTCTURK:
            raise ValueError(f"{self.follower_exchange} is not supported")

    def is_valid(self):
        self.is_valid_exchanges()
        return self.input.is_valid()
