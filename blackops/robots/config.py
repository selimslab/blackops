import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import pydantic
from pydantic import BaseModel, Field

from blackops.domain.symbols import ALL_SYMBOLS, BTCTURK_TRY_BASES, SUPPORTED_BRIDDGES
from blackops.exchanges.factory import ExchangeType, NetworkType

MAX_SPEND_ALLOWED = 200000


class StrategyType(str, Enum):
    SLIDING_WINDOW = "sliding_window"


class StrategyConfigBase(BaseModel):
    type: str
    created_at: str = Field(default_factory=lambda: str(datetime.now().isoformat()))
    sha: str = Field(default_factory=lambda: uuid.uuid4().hex)

    def is_valid(self):
        raise NotImplementedError


class SlidingWindowConfig(StrategyConfigBase):

    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    base: str = Field(..., example="ETH")
    quote: str = Field(..., example="TRY")
    bridge: Optional[str] = Field(default=None, example="USDT")
    use_bridge = True

    # network : NetworkType = NetworkType.TESTNET
    testnet = True
    use_real_money = False

    leader_exchange: ExchangeType = ExchangeType.BINANCE
    follower_exchange: ExchangeType = ExchangeType.BTCTURK

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
        if self.leader_exchange != ExchangeType.BINANCE:
            raise ValueError(f"{self.leader_exchange} is not supported")

        if self.follower_exchange != ExchangeType.BTCTURK:
            raise ValueError(f"{self.follower_exchange} is not supported")

    def is_valid_mode(self):
        if self.testnet == self.use_real_money:
            return Exception("test or real money?")

    def is_valid_params(self):
        if self.max_usable_quote_amount_y > MAX_SPEND_ALLOWED:
            raise Exception(
                f"you will spend more than {MAX_SPEND_ALLOWED}, are you sure?"
            )

        if self.credit < 0:
            raise Exception(f"credit must be positive")

        if self.step_constant_k < 0:
            raise Exception(f"step_constant_k must be positive")

        if self.base_step_qty < 0:
            raise Exception(f"base_step_qty must be positive")

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
