from decimal import Decimal
from typing import Optional

from pydantic import Field

from src.exchanges.factory import ExchangeType
from src.stgs.base import StrategyInputBase, StrategyType
from src.stgs.symbols import ALL_SYMBOLS, BTCTURK_TRY_BASES, SUPPORTED_BRIDDGES


class SlidingWindowInput(StrategyInputBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    base: str = Field(..., example="ETH")
    quote: str = Field(..., example="TRY")

    bridge: Optional[str] = Field(default=None, example="USDT")
    bridge_exchange: Optional[ExchangeType] = ExchangeType.BTCTURK

    use_bridge = True
    testnet = False
    use_real_money = True

    max_step: Decimal = Decimal(8)

    quote_step_qty: Decimal = Decimal(5000)

    margin_bps: Decimal = Decimal("1")

    def is_valid_type(self):
        if self.type != StrategyType.SLIDING_WINDOW:
            raise ValueError(f"{self.type} is not a valid strategy type")

    def is_valid_mode(self):
        if self.testnet == self.use_real_money:
            raise Exception("test or real money?")

    def is_valid_symbols(self):
        if self.base not in ALL_SYMBOLS:
            raise ValueError(f"{self.base} is not a valid symbol")

        if self.quote not in ALL_SYMBOLS:
            raise ValueError(f"{self.quote} is not a valid symbol")

        if self.base == self.quote:
            raise ValueError(f"{self.base} and {self.quote} cannot be the same")

        if self.base not in BTCTURK_TRY_BASES:
            raise ValueError(f"{ExchangeType.BTCTURK} has no {self.base} / TRY pair ")

    def is_valid_bridge(self):
        if self.use_bridge is False and self.bridge:
            raise ValueError(
                "do you want to use bridge? if yes, set use_bridge to true, if no, do not send a bridge symbol"
            )

        if self.use_bridge is True and not self.bridge:
            raise ValueError(
                "do you want to use bridge? if yes, set use_bridge to true, if no, do not send a bridge symbol"
            )

        if self.bridge and self.bridge not in SUPPORTED_BRIDDGES:
            raise ValueError(f"{self.bridge} is not a supported bridge")

        if (
            self.bridge_exchange
            and self.bridge_exchange
            and self.bridge_exchange
            not in [
                ExchangeType.BINANCE,
                ExchangeType.BTCTURK,
            ]
        ):
            raise ValueError(
                f"{self.bridge_exchange} is not a supported bridge exchange"
            )

        if self.bridge and self.use_bridge and not self.bridge_exchange:
            raise ValueError(f"bridge exchange is required if you want to use a bridge")

    def is_valid_params(self):
        if self.margin_bps < 1:
            raise Exception("margin_bps must be greater than 1")
        if self.margin_bps > 3:
            raise Exception("margin_bps must be less than 3")

        if self.max_step < 2:
            raise Exception("max_step must be greater than 1")
        if self.max_step > 12:
            raise Exception("max_step must be less than 12")

    def is_valid(self):
        self.is_valid_type()
        self.is_valid_mode()
        self.is_valid_symbols()
        self.is_valid_bridge()
        self.is_valid_params()
