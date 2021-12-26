from abc import ABC
from dataclasses import dataclass


@dataclass
class RobotBase(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    async def run(self) -> None:
        ...

    def should_long(self) -> bool:
        ...

    def should_short(self) -> bool:
        ...

    async def long(self) -> None:
        ...

    async def short(self) -> None:
        ...

    async def close(self) -> None:
        ...

    def get_orders(self) -> list:
        return []
