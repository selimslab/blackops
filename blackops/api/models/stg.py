import uuid
from decimal import Decimal
from typing import Union

import simplejson as json
from pydantic import BaseModel, Field

from blackops.domain.symbols import ALL_SYMBOLS, BTCTURK_TRY_BASES, SUPPORTED_BRIDDGES

STG_MAP = "STG_MAP"

NO_HASH = "NO_HASH"

MAX_SPEND_ALLOWED = 100000


class ImmutableModel(BaseModel):
    class Config:
        allow_mutation = False


class StrategyBase(ImmutableModel):
    type: str
    # uid: str = Field(default_factory=lambda: str(uuid.uuid4()), const=True, description="unique id")

    def is_valid(self):
        raise NotImplementedError


class SlidingWindow(StrategyBase):

    type = Field("sliding_window", const=True, example="sliding_window")

    base: str = Field(..., example="BTC")
    quote: str = Field(..., example="TRY")

    testnet = True

    use_real_money = False

    max_usable_quote_amount_y: Decimal = Field(
        description="eg. use max 5000 TRY for this strategy, if you have less balance, you will get an error when you run the stg",
        example="5000",
    )

    step_count: Decimal = Field(
        description="eg. spend your max_usable_quote_amount in 20 steps", example="20"
    )

    step_constant_k: Decimal = Field(
        ...,
        example="0.001",
        description="slide down by this amount after every buy, slide up by this amount after every sell",
    )

    credit: Decimal = Field(
        ...,
        example="0.001",
        description="defines window height, high=mid + credit, low = mid-credit",
    )

    leader_exchange = "binance"
    follower_exchange = "btcturk"

    description: str = "slide down as you buy, slide up as you sell"

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
        if not self.testnet:
            raise ValueError("real time not supported yet")

        if self.testnet == self.use_real_money:
            return Exception("test or real money ? this is very important")

    def is_valid_params(self):

        if self.max_usable_quote_amount_y >= MAX_SPEND_ALLOWED:
            raise Exception(
                f"you will spend more than {MAX_SPEND_ALLOWED}, are you sure?"
            )

    def is_valid(self):

        self.is_valid_mode()
        self.is_valid_exchanges()
        self.is_valid_symbols()
        self.is_valid_params()


class SlidingWindowWithBridge(SlidingWindow):
    type = Field("sliding_window_with_bridge", const=True)

    bridge: str

    def is_valid_bridge(self):
        if self.bridge not in SUPPORTED_BRIDDGES:
            raise ValueError(f"{self.bridge} is not a supported bridge")

    def is_valid(self):
        super().is_valid()
        self.is_valid_bridge()


Strategy = Union[SlidingWindowWithBridge, SlidingWindow]
