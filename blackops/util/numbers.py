from decimal import Decimal


def decimal_division(a, b):
    return Decimal(a) / Decimal(b)


DECIMAL_2 = Decimal(2)


def decimal_half(a):
    return Decimal(a) / DECIMAL_2


def decimal_mid(a, b):
    return (Decimal(a) + Decimal(b)) / DECIMAL_2
