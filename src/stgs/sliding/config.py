from decimal import Decimal

from pydantic import BaseModel, Field

from src.exchanges.factory import ExchangeType
from src.idgen import dict_to_hash
from src.numberops import round_decimal_half_up
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import SlidingWindowInput


class SlidingWindowConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    base_step_qty: Decimal = Decimal(0)
    base_step_qty_reference_price: Decimal

    input: SlidingWindowInput

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        sha = dict_to_hash(self.input.dict())[:7]
        mode = "testnet" if self.input.testnet else "real"
        self.sha = f"{sha}_{self.input.base}_{self.input.quote}_{mode}"

        self.set_base_step_qty(self.base_step_qty_reference_price)

    def set_base_step_qty(self, price: Decimal) -> None:
        self.base_step_qty_reference_price = price
        self.base_step_qty = round_decimal_half_up(
            self.input.quote_step_qty / self.base_step_qty_reference_price
        )

    def is_valid_exchanges(self):
        if self.leader_exchange != ExchangeType.BINANCE:
            raise ValueError(f"{self.leader_exchange} is not supported")

        if self.follower_exchange != ExchangeType.BTCTURK:
            raise ValueError(f"{self.follower_exchange} is not supported")

    def is_valid_params(self):
        if self.base_step_qty <= 0:
            raise Exception("base_step_qty must be greater than 0")

    def is_valid(self):
        self.is_valid_exchanges()
        return self.input.is_valid()
