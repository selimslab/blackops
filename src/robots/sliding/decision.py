import decimal
from dataclasses import dataclass
from decimal import Decimal

from src.domain import BPS
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import CreditConstants, Credits, FeeBPS, Prices, Signals, TargetPrices


@dataclass
class DecisionAPI:
    credit_constants: CreditConstants = CreditConstants()

    def set_credits(self, config: LeaderFollowerConfig):
        # self.credits.maker = (
        #     (maker_fee_bps + taker_fee_bps) / Decimal(2)
        # ) + self.config.margin_bps

        window = 2 * (FeeBPS.taker + config.margin_bps)
        self.credit_constants.taker.sell = Decimal(6)
        self.credit_constants.taker.buy = (
            window - self.credit_constants.taker.sell
        )  # 14
        self.credit_constants.taker.hold = Decimal(1)

    def get_credits(self, mid: Decimal, current_step: Decimal) -> Credits:
        hold_risk = self.credit_constants.taker.hold * current_step
        midbps = mid * BPS
        return Credits(
            buy=(self.credit_constants.taker.buy - hold_risk) * midbps,
            sell=(self.credit_constants.taker.sell + hold_risk) * midbps,
        )

    def get_signals(
        self, mid: Decimal, ask: Decimal, bid: Decimal, credits: Credits
    ) -> Signals:
        return Signals(sell=(bid - mid) / credits.sell, buy=(mid - ask) / credits.buy)

    def get_precision_price(self, price: Decimal, reference: Decimal) -> Decimal:
        return price.quantize(reference, rounding=decimal.ROUND_DOWN)

    def get_target_prices(
        self, mid: Decimal, ask: Decimal, bid: Decimal, credits: Credits
    ) -> TargetPrices:
        return TargetPrices(
            taker=Prices(
                sell=self.get_precision_price(mid + credits.sell, bid),
                buy=self.get_precision_price(mid - credits.buy, ask),
            ),
            maker=None,
        )
