from abc import ABC
from dataclasses import dataclass


@dataclass
class StrategyBase(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    def run(self):
        ...

    def should_long(self):
        ...

    def should_short(self):
        ...
