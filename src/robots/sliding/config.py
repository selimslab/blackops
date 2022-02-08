from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain import BPS


class UnitSignalBPS(BaseModel):
    sell: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)
    step: Decimal = Decimal(0)
    slope_risk: Decimal = Decimal(0)


class Settings(BaseModel):
    sell_step: Decimal = Decimal(2)

    max_step: Decimal = Decimal(20)
    quote_step_qty: Decimal = Decimal(2000)

    unit_signal_bps: UnitSignalBPS = UnitSignalBPS(
        buy=Decimal(13) * BPS,
        sell=Decimal(5) * BPS,
        step=Decimal("0.5") * BPS,
        slope_risk=Decimal("0.8") * BPS,
    )

    min_sell_qty: Decimal = Decimal(400)
    min_buy_qty: Decimal = Decimal(2000)
    max_spread_bps: Decimal = Decimal(15)


settings = Settings()
