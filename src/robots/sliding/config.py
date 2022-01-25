from decimal import Decimal

from pydantic import BaseModel, Field

from src.exchanges.factory import ExchangeType
from src.stgs.base import StrategyConfigBase, StrategyType

from .inputs import LeaderFollowerInput


class Credits(BaseModel):
    maker: Decimal = Decimal(0)
    taker: Decimal = Decimal(0)
    step: Decimal = Decimal(0)
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


class LeaderFollowerConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    leader_exchange: ExchangeType = Field(ExchangeType.BINANCE)
    follower_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    bridge: str = Field("USDT")
    bridge_exchange: ExchangeType = Field(ExchangeType.BTCTURK)

    max_step: Decimal = Decimal(6)

    quote_step_qty: Decimal = Decimal(8000)

    min_sell_qty: Decimal = Decimal(400)
    min_buy_qty: Decimal = Decimal(3000)

    testnet = False

    credits: Credits = Credits(
        step=Decimal("0.25"),
        sell=Decimal(6),
        buy=Decimal(18),
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