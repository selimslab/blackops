from dataclasses import dataclass


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
