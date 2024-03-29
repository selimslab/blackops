from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain import BPS


class UnitSignalBPS(BaseModel):
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)
    step: Decimal = Decimal(0)
    # slope_risk: Decimal = Decimal(0)
    # spread_risk: Decimal = Decimal(0)
    # ratio_risk: Decimal = Decimal(0)


class Settings(BaseModel):

    max_step: Decimal = Decimal(20)
    quote_step_qty: Decimal = Decimal(1000)

    sell_step: Decimal = Decimal(2)
    min_sell_qty: Decimal = Decimal(300)

    unit_signal_bps: UnitSignalBPS = UnitSignalBPS(
        buy=Decimal(12) * BPS,
        sell=Decimal(6) * BPS,
        step=Decimal(1) * BPS,
        # slope_risk=Decimal(4) * BPS,
        # spread_risk=Decimal(2) * BPS,
        # ratio_risk=Decimal(3) * BPS,
    )
    max_spread_bps: Decimal = Decimal(15)


settings = Settings()
