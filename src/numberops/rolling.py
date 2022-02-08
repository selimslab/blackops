import collections
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RollingMean:
    maxlen: int
    total: Decimal = Decimal(0)
    count: Decimal = Decimal(0)

    def __post_init__(self):
        self.values = collections.deque(maxlen=self.maxlen)

    def add(self, value):
        if self.count < self.maxlen:
            self.values.append(value)
            self.count += 1
        else:
            self.total -= self.values.popleft()
            self.values.append(value)

        self.total += value

    def get_average(self):
        return self.total / self.count
