from dataclasses import dataclass
from decimal import Decimal

from src.domain import BPS, maker_fee_bps, taker_fee_bps
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import Credits


@dataclass
class DecisionAPI:
    credits: Credits = Credits()

    def set_credits(self, config: LeaderFollowerConfig):
        # self.credits.maker = (
        #     (maker_fee_bps + taker_fee_bps) / Decimal(2)
        # ) + self.config.margin_bps

        self.credits.taker = taker_fee_bps + config.margin_bps
        self.credits.step = self.credits.taker / config.max_step
        self.credits.sell = self.credits.taker - Decimal("4.5")
        self.credits.buy = self.credits.taker + Decimal("4.5")

    def get_sell_signal_min(self, mid: Decimal) -> Decimal:
        return self.credits.sell * mid * BPS

    def get_buy_signal_min(self, mid: Decimal) -> Decimal:
        return self.credits.buy * mid * BPS

    def get_risk_adjusted_mid(self, mid: Decimal, current_step: Decimal) -> Decimal:
        hold_risk = self.credits.step * current_step * mid * BPS
        return mid - hold_risk
