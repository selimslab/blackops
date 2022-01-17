import decimal
from decimal import Decimal

half_up_rounding_context = decimal.Context(prec=1, rounding=decimal.ROUND_HALF_UP)

floor_rounding_context = decimal.Context(prec=2, rounding=decimal.ROUND_FLOOR)


def round_decimal_half_up(d: Decimal) -> Decimal:
    """Round half up with precision 1
    0.00378502 -> 0.004

    5063291.139240 -> 5 million
    """
    return d.normalize(half_up_rounding_context)


def round_decimal_floor(d: Decimal) -> Decimal:
    """Round half up with precision 1
    0.00378502 -> 0.004

    5063291.139240 -> 5 million
    """
    return d.normalize(floor_rounding_context)


def get_precision(d: Decimal):
    sign, digit, exponent = d.as_tuple()
    return exponent


def get_bps(d: Decimal) -> Decimal:
    sign, digit, exponent = d.as_tuple()
    return Decimal(str(10 ** exponent))


def one_bps_lower(d: Decimal) -> Decimal:
    bps = get_bps(d)
    return d - bps


def one_bps_higher(d: Decimal) -> Decimal:
    bps = get_bps(d)
    return d + bps
