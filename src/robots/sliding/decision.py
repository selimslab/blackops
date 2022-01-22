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

        window = 2 * (taker_fee_bps + config.margin_bps)
        self.credits.taker.sell = Decimal(6)
        self.credits.taker.buy = window - self.credits.taker.sell  # 14
        self.credits.taker.hold = Decimal(1)

    def get_sell_signal_min(self, mid: Decimal) -> Decimal:
        return self.credits.taker.sell * mid * BPS

    def get_buy_signal_min(self, mid: Decimal) -> Decimal:
        return self.credits.taker.buy * mid * BPS

    def get_risk_adjusted_mid(self, mid: Decimal, current_step: Decimal) -> Decimal:
        hold_risk = self.credits.taker.hold * current_step * mid * BPS
        return mid - hold_risk
