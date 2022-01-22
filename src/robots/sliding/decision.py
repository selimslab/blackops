import decimal
from dataclasses import dataclass, field
from decimal import Decimal

from src.domain import BPS
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import Credits, CreditsBPS, FeeBPS, Prices, Signals, TargetPrices


@dataclass
class DecisionAPI:
    credits: Credits = field(default_factory=Credits)

    def set_credits(self, config: LeaderFollowerConfig):
        # self.credits.maker = (
        #     (maker_fee_bps + taker_fee_bps) / Decimal(2)
        # ) + self.config.margin_bps

        window = Decimal(2) * (FeeBPS.taker + config.margin_bps)
        self.credits.taker.sell = Decimal(6)
        self.credits.taker.buy = window - self.credits.taker.sell  # 14
        self.credits.taker.hold = Decimal(1)

    def get_credits(self, current_step: Decimal) -> Credits:
        hold_risk = self.credits.taker.hold * current_step
        return Credits(
            taker=CreditsBPS(
                buy=(self.credits.taker.buy + hold_risk),
                sell=(self.credits.taker.sell - hold_risk),  # make selling easier
            )
        )

    def get_signals(
        self, mid: Decimal, ask: Decimal, bid: Decimal, credits: Credits
    ) -> Signals:
        midbps = mid * BPS
        return Signals(
            sell=(bid - mid) / credits.taker.sell * midbps,
            buy=(mid - ask) / credits.taker.buy * midbps,
        )

    def get_precision_price(self, price: Decimal, reference: Decimal) -> Decimal:
        return price.quantize(reference, rounding=decimal.ROUND_DOWN)

    def get_target_prices(
        self, mid: Decimal, ask: Decimal, bid: Decimal, credits: Credits
    ) -> TargetPrices:
        midbps = mid * BPS
        taker_sell = (Decimal(1) + credits.taker.sell) * midbps
        taker_buy = (Decimal(1) - credits.taker.buy) * midbps

        return TargetPrices(
            taker=Prices(
                sell=self.get_precision_price(taker_sell, bid),
                buy=self.get_precision_price(taker_buy, ask),
            )
        )
