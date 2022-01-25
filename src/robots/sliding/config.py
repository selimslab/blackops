from decimal import Decimal

from pydantic import BaseModel, Field

from src.exchanges.factory import ExchangeType
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import LeaderFollowerInput


class Credits(BaseModel):
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


class LeaderFollowerConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge: str = Field("USDT")
    bridge_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    max_step: Decimal = Decimal(3)

    quote_step_qty: Decimal = Decimal(16000)

    min_sell_qty: Decimal = Decimal(500)
    min_buy_qty: Decimal = Decimal(4000)

    testnet = False

    credits: Credits = Credits(
        sell=Decimal(5),
        buy=Decimal(15),
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
