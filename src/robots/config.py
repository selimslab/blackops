import decimal
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

import pydantic
from pydantic import BaseModel, Field

from src.domain.asset import PIP
from src.domain.symbols import ALL_SYMBOLS, BTCTURK_TRY_BASES, SUPPORTED_BRIDDGES
from src.exchanges.factory import ExchangeType, NetworkType

MAX_SPEND_ALLOWED = 200000


class StrategyType(str, Enum):
    SLIDING_WINDOW = "sliding_window"


class StrategyConfigBase(BaseModel):
    type: str
    created_at: str = Field(default_factory=lambda: str(datetime.now().isoformat()))
    sha: str = Field(default_factory=lambda: uuid.uuid4().hex)

    def is_valid(self):
        raise NotImplementedError


class SleepSeconds(BaseModel):
    update_balances: float = 0.72
    cancel_all_open_orders: float = 2
    broadcast_stats: float = 2


class SlidingWindowConfig(StrategyConfigBase):

    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    base: str = Field(..., example="ETH")
    quote: str = Field(..., example="TRY")

    bridge: Optional[str] = Field(default=None, example="USDT")
    bridge_exchange: Optional[ExchangeType] = ExchangeType.BINANCE
    use_bridge = True

    # network : NetworkType = NetworkType.TESTNET
    testnet = True
    use_real_money = False

    leader_exchange: ExchangeType = ExchangeType.BINANCE
    follower_exchange: ExchangeType = ExchangeType.BTCTURK

    max_usable_quote_amount_y: Decimal = Decimal(1000)

    quote_step_qty: Decimal = Decimal(1500)

    step_pip: Decimal = Decimal("2.5")

    credit_k: Decimal = Decimal(5)

    reference_price_for_parameters: Optional[Decimal] = None

    base_step_qty: Decimal = Decimal(0)

    step_constant_k: Decimal = Decimal(0)

    credit: Decimal = Decimal(0)

    sleep_seconds: SleepSeconds = Field(default_factory=SleepSeconds)

    def set_params_auto(self):
        if not self.reference_price_for_parameters:
            raise Exception("reference_price_for_parameters is required")
        num = self.quote_step_qty / self.reference_price_for_parameters
        context = decimal.Context(prec=5, rounding=decimal.ROUND_HALF_UP)
        self.base_step_qty = num.normalize(context)
        self.step_constant_k = self.step_pip * PIP * self.reference_price_for_parameters
        self.credit = self.credit_k * self.step_constant_k

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
        if not self.max_usable_quote_amount_y:
            raise Exception("max_usable_quote_amount_y is required")

        if self.max_usable_quote_amount_y > MAX_SPEND_ALLOWED:
            raise Exception(
                f"you will spend more than {MAX_SPEND_ALLOWED}, are you sure?"
            )

        if not self.credit:
            raise Exception("credit is required")

        if self.credit < 0:
            raise Exception(f"credit must be positive")

        if not self.step_constant_k:
            raise Exception("step_constant_k is required")

        if self.step_constant_k < 0:
            raise Exception(f"step_constant_k must be positive")

        if not self.base_step_qty:
            raise Exception("base_step_qty is required")

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

        if self.bridge_exchange and self.bridge_exchange not in [
            ExchangeType.BINANCE,
            ExchangeType.BTCTURK,
        ]:
            raise ValueError(
                f"{self.bridge_exchange} is not a supported bridge exchange"
            )

        if self.bridge and self.use_bridge and not self.bridge_exchange:
            raise ValueError(f"bridge exchange is required if you want to use a bridge")

    def is_valid(self):

        self.is_valid_mode()
        self.is_valid_exchanges()
        self.is_valid_symbols()
        self.is_valid_params()

        if self.bridge:
            self.is_valid_bridge()


StrategyConfig = SlidingWindowConfig

STRATEGY_CLASS = {StrategyType.SLIDING_WINDOW: SlidingWindowConfig}
