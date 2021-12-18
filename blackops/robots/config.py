from decimal import Decimal
from enum import Enum
from typing import Optional

import simplejson as json
from pydantic import BaseModel, Field

from blackops.domain.symbols import ALL_SYMBOLS, BTCTURK_TRY_BASES, SUPPORTED_BRIDDGES

MAX_SPEND_ALLOWED = 200000


class StrategyType(Enum):
    SLIDING_WINDOW = "sliding_window"


class ImmutableModel(BaseModel):
    class Config:
        allow_mutation = False


class StrategyConfigBase(BaseModel):
    type: str
    # uid: str = Field(default_factory=lambda: str(uuid.uuid4()), const=True, description="unique id")

    def is_valid(self):
        raise NotImplementedError


class SlidingWindowConfig(StrategyConfigBase):

    type = Field("sliding_window", const=True, example="sliding_window")

    base: str = Field(..., example="DOGE")
    quote: str = Field(..., example="TRY")
    bridge: Optional[str] = Field(default=None, example="USDT")
    use_bridge = True

    testnet = True

    use_real_money = False

    max_usable_quote_amount_y: Decimal = Field(
        description="eg. use max 5000 TRY for this strategy, if you have less balance, you will get an error when you run the stg",
        example="24000",
    )

    base_step_qty: Decimal = Field(
        description="eg. buy 100 MANA per step", example="100"
    )

    step_constant_k: Decimal = Field(
        ...,
        example="0.2",
        description="slide down by this amount after every buy, slide up by this amount after every sell",
    )

    credit: Decimal = Field(
        ...,
        example="0.75",
        description="defines window height, high=mid + credit, low = mid-credit",
    )

    leader_exchange = "binance"
    follower_exchange = "btcturk"

    description: str = "slide down as you buy, slide up as you sell"

    sha: Optional[str] = None

    def is_valid_symbols(self):
        if self.base not in ALL_SYMBOLS:
            raise ValueError(f"{self.base} is not a valid symbol")

        if self.quote not in ALL_SYMBOLS:
            raise ValueError(f"{self.quote} is not a valid symbol")

        if self.base == self.quote:
            raise ValueError(f"{self.base} and {self.quote} cannot be the same")

        if self.base not in BTCTURK_TRY_BASES:
            raise ValueError(f"{self.follower_exchange} has no {self.base} / TRY pair ")

        if self.base not in BTCTURK_TRY_BASES:
            raise ValueError(f"{self.follower_exchange} has no {self.base} / TRY pair ")

    def is_valid_exchanges(self):
        if self.leader_exchange != "binance":
            raise ValueError(f"{self.leader_exchange} is not supported")

        if self.follower_exchange != "btcturk":
            raise ValueError(f"{self.follower_exchange} is not supported")

    def is_valid_mode(self):
        if self.testnet == self.use_real_money:
            return Exception("test or real money?")

    def is_valid_params(self):
        if self.max_usable_quote_amount_y > MAX_SPEND_ALLOWED:
            raise Exception(
                f"you will spend more than {MAX_SPEND_ALLOWED}, are you sure?"
            )

    def is_valid_bridge(self):
        if self.use_bridge is False and self.bridge:
            raise ValueError(
                "do you want to use bridge? if yes, set use_bridge to true, if no, do not send a bridge symbol"
            )

        if self.use_bridge is True and not self.bridge:
            raise ValueError(
                "do you want to use bridge? if yes, set use_bridge to true, if no, do not send a bridge symbol"
            )

        if self.bridge not in SUPPORTED_BRIDDGES:
            raise ValueError(f"{self.bridge} is not a supported bridge")

    def is_valid(self):

        self.is_valid_mode()
        self.is_valid_exchanges()
        self.is_valid_symbols()
        self.is_valid_params()

        if self.bridge:
            self.is_valid_bridge()


StrategyConfig = SlidingWindowConfig

STRATEGY_CLASS = {StrategyType.SLIDING_WINDOW: SlidingWindowConfig}
