from decimal import Decimal
from .main import round_decimal

def test_round():
    shib = Decimal("0.00041596")
    btc = Decimal("793648")
    step_try = Decimal("3000")
    print("shib step", step_try/shib)
    print("btc step", step_try/btc)

    assert round_decimal(Decimal("0.00378502")) == Decimal("0.004")
    assert round_decimal(Decimal("5063291.139240")) == Decimal("5000000")
    assert round_decimal(step_try/shib) == Decimal('7000000')
    assert round_decimal(step_try/btc) == Decimal("0.004")
