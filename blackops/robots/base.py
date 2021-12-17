from abc import ABC
from dataclasses import dataclass


@dataclass
class RobotBase(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    async def run(self):
        ...

    def should_long(self):
        ...

    def should_short(self):
        ...

    async def long(self):
        ...

    async def short(self):
        ...
