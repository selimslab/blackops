from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .exch import Exchange
from .asset import Asset, AssetPair


@dataclass
class Strategy(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    name: str

    def start(self):
        ...

    def should_long(self):
        return ...

    def should_short(self):
        return ...


t
