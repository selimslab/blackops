from decimal import Decimal

from pydantic import BaseModel, Field

from src.exchanges.factory import ExchangeType
from src.idgen import dict_to_hash
from src.numberops import round_decimal_half_up
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import LeaderFollowerInput


class LeaderFollowerConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge: str = Field("USDT")
    bridge_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    max_step: Decimal = Decimal(6)

    quote_step_qty: Decimal = Decimal(12000)

    margin_bps: Decimal = Decimal(1)

    min_sell_qty: Decimal = Decimal(300)

    testnet = False

    input: LeaderFollowerInput

    def __init__(self, **data):
        super().__init__(**data)

        self.is_valid()

        # sha = dict_to_hash(self.input.dict())[:7]
        mode = "test" if self.input.testnet else "real"
        self.sha = f"{self.input.base}_{self.input.quote}_{mode}"

    def is_valid(self):
        return self.input.is_valid()
