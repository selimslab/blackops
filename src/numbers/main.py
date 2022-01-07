import decimal
from decimal import Decimal

rounding_context = decimal.Context(prec=1, rounding=decimal.ROUND_HALF_UP)

def round_decimal(d:Decimal)->Decimal:
    """ Round half up with precision 1 
    0.00378502 -> 0.004

    5063291.139240 -> 5 million 
    """
    return d.normalize(rounding_context)



