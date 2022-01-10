from abc import ABC
from dataclasses import dataclass


@dataclass
class RobotBase(ABC):

    # pair: AssetPair  # base and quote currencies

    # a stg may use many pairs, many streams, many exchanges to make a decision

    async def long(self) -> None:
        ...

    async def short(self) -> None:
        ...

    async def close(self) -> None:
        ...
