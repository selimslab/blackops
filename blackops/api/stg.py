import hashlib
from decimal import Decimal
from enum import Enum
from typing import Any, List, Mapping, Optional, OrderedDict, Union

import simplejson as json
from pydantic import BaseModel, Field

STG_MAP = "STG_MAP"

NO_HASH = "NO_HASH"


class Symbol:
    ...

class ImmutableModel(BaseModel):

    class Config:
        allow_mutation = False


class StrategyBase(ImmutableModel):
    type: str

    def is_valid(self):
        raise NotImplementedError


class OtherStrategy(StrategyBase):
    type = "other_stg"

    class Config:
        schema_extra = {
            "example": {
                "type": "other",
                "base": "BTC",
                "quote": "TRY",
                "max_usable_quote_amount": 5000,
                "max_spend_per_step": 100,
            }
        }


class SlidingWindowStrategy(StrategyBase):

    type = "sliding_window"

    base: str
    quote: str
    bridge: Optional[str] = Field(
        None,
        description="set only if there is no direct quote on binance",
        example="USDT",
    )

    testnet = True

    use_real_money = False

    max_usable_quote_amount: Decimal = Field(
        description="eg. use max 5000 TRY for this strategy", example="5000"
    )
    max_spend_per_step: Decimal = Field(
        description="eg. spend max 200 TRY per step", example="200"
    )

    description: Optional[str] = "slide down as you buy, slide up as you sell"


    def is_valid(self):
        if self.max_spend_per_step > self.max_usable_quote_amount:
            raise Exception("max_spend_per_step is lower than max_usable_quote_amount")

        if self.testnet == self.use_real_money:
            return Exception("test or real money ??")

    class Config:
       
        # show the required fields as an example in openapi docs 
        # so you can directly edit 
        schema_extra = {
            "example": {
                "type": "sliding_window",
                "testnet": True,
                "use_real_money": False,
                "base": "BTC",
                "quote": "TRY",
                "bridge": "USDT",
                "max_usable_quote_amount": 5000,
                "max_spend_per_step": 100,
            }
        }


Strategy = Union[SlidingWindowStrategy, OtherStrategy]
