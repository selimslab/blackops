import decimal
from decimal import Decimal

from .main import one_bps_lower, round_decimal_floor, round_decimal_half_up


def get_precise_price(price: Decimal, reference: Decimal) -> Decimal:
    return price.quantize(reference, rounding=decimal.ROUND_HALF_DOWN)


def test_round():
    shib = Decimal("0.00041596")
    btc = Decimal("793648")
    step_try = Decimal("3000")
    print("shib step", step_try / shib)
    print("btc step", step_try / btc)

    # getcontext().prec = 9
    # assert Decimal("42.83") * Decimal("2.3445564") == Decimal("43.833")

    assert round(float(Decimal(200.00))) == 200
    assert round(float(Decimal(0.23))) == int(Decimal(0.23))

    d = Decimal("0.0037850200")
    assert float(d) == 0.00378502
    assert get_precise_price(Decimal("0.0037850200"), Decimal("0.0037")) == Decimal(
        "0.0038"
    )

    assert Decimal("43.23313072").quantize(
        Decimal("11.547"), rounding=decimal.ROUND_DOWN
    ) == Decimal("43.233")
    assert round_decimal_floor(Decimal("553.5")) == Decimal("500")
    assert round_decimal_floor(Decimal("5063291.139240")) == Decimal("5000000")

    d = Decimal("3.32608957")
    assert round_decimal_half_up(d) == Decimal("3")

    assert round(d) == Decimal("3")

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

    assert get_precise_price(Decimal("2.834567"), Decimal("2.833")) == Decimal("2.835")
    assert get_precise_price(Decimal("2.863937"), Decimal("2.833")) == Decimal("2.864")
