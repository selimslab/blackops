from dataclasses import dataclass


@dataclass
class B:
    x: int


@dataclass
class A:
    x: int = 5

    def __post_init__(self):
        self.b = B(self.x)


a = A()
print(a.x, a.b.x)
a.x = 3
print(a.x, a.b.x)
