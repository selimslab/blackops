from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.domain.asset import Asset, AssetPair
from src.numbers import round_decimal
from src.idgen import dict_to_hash
from src.exchanges.btcturk import btc_real_api_client_public
from .inputs import SlidingWindowInput

from src.stgs.base import StrategyType, StrategyConfigBase



class SleepSeconds(BaseModel):
    update_balances: float = 0.72
    cancel_all_open_orders: float = 2
    broadcast_stats: float = 2

class SlidingWindowConfig(StrategyConfigBase):
    type: StrategyType = Field(StrategyType.SLIDING_WINDOW, const=True)

    pair: Optional[AssetPair] = None

    reference_price: Optional[Decimal] = None

    base_step_qty: Decimal = Decimal(0)

    credit_bps: Decimal = Decimal(0)

    sleep_seconds: SleepSeconds = Field(default_factory=SleepSeconds)

    input:SlidingWindowInput


    async def __post_init__(self):

        self.is_valid()

        sha = dict_to_hash(self.input.dict())[:7]
        self.sha = sha

        self.pair = AssetPair(Asset(symbol=self.input.base), Asset(symbol=self.input.quote))
        
        ticker = await btc_real_api_client_public.get_ticker(self.pair)
        if not ticker:
            raise Exception("couldn't read price, please try again")

        self.set_params(ticker)

    def set_params(self, ticker):
        self.credit_bps = 2 * self.input.fee_bps + self.input.margin_bps
        self.base_step_qty = round_decimal(self.input.quote_step_qty / ticker)
        self.reference_price = ticker

    def is_valid(self):
        return self.input.is_valid()