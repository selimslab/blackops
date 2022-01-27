from dataclasses import dataclass
from re import A


@dataclass
class B:
    x: int


@dataclass
class Asset:
    free: int = 5


a = Asset()
lst = [a]
a.free = 4345

print(lst)

b = a

b.free = 0

print(lst)
