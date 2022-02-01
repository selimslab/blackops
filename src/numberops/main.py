import decimal
from decimal import Decimal

half_up_rounding_context = decimal.Context(prec=1, rounding=decimal.ROUND_HALF_UP)

floor_rounding_context = decimal.Context(prec=1, rounding=decimal.ROUND_DOWN)


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


def get_smallest_exponent(d: Decimal) -> Decimal:
    sign, digit, exponent = d.as_tuple()
    return Decimal(str(10 ** exponent))


def n_bps_higher(d: Decimal, n: Decimal) -> Decimal:
    bps = get_smallest_exponent(d)
    return d + n * bps


def n_bps_lower(d: Decimal, n: Decimal) -> Decimal:
    bps = get_smallest_exponent(d)
    return d - n * bps


def one_bps_lower(d: Decimal) -> Decimal:
    bps = get_smallest_exponent(d)
    return d - bps


def one_bps_higher(d: Decimal) -> Decimal:
    bps = get_smallest_exponent(d)
    return d + bps
