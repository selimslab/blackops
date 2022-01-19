import asyncio
from dataclasses import dataclass, field


@dataclass
class Locks:
    buy: asyncio.Lock = field(default_factory=asyncio.Lock)
    sell: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel: asyncio.Lock = field(default_factory=asyncio.Lock)
    rate_limit: asyncio.Lock = field(default_factory=asyncio.Lock)
    read: asyncio.Lock = field(default_factory=asyncio.Lock)
