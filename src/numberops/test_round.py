from decimal import Decimal

from .main import one_bps_lower, round_decimal_half_up


def test_round():
    shib = Decimal("0.00041596")
    btc = Decimal("793648")
    step_try = Decimal("3000")
    print("shib step", step_try / shib)
    print("btc step", step_try / btc)

    assert round_decimal_half_up(Decimal("3.32608957")) == Decimal("3")

    assert round_decimal_half_up(Decimal("0.00378502")) == Decimal("0.004")
    assert round_decimal_half_up(Decimal("5063291.139240")) == Decimal("5000000")
    assert round_decimal_half_up(step_try / shib) == Decimal("7000000")
    assert round_decimal_half_up(step_try / btc) == Decimal("0.004")

    assert one_bps_lower(Decimal("0.00378")) == Decimal("0.00377")
    assert one_bps_lower(Decimal("54.67")) == Decimal("54.66")
    assert one_bps_lower(Decimal("0.000001")) == Decimal("0")
    assert one_bps_lower(Decimal("5456")) == Decimal("5455")
    assert one_bps_lower(Decimal("5456000")) == Decimal("5455999")
    assert one_bps_lower(Decimal("0.00378000")) == Decimal("0.00377999")
