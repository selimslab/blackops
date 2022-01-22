import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.environment import sleep_seconds

from .models import MarketPrices, stopwatches


@dataclass
class PriceAPI:
    bridge: Optional[Decimal] = None
    follower: MarketPrices = field(default_factory=MarketPrices)

    async def update_bridge(self, quote: Decimal):
        async with stopwatches.bridge.stopwatch(
            self.clear_bridge, sleep_seconds.clear_follower_prices
        ):
            self.bridge = quote

    def clear_bridge(self):
        self.bridge = None

    def apply_bridge_to_price(
        self, mid: Decimal, use_bridge: bool
    ) -> Optional[Decimal]:
        if use_bridge:
            if self.bridge:
                return mid * self.bridge
            return None
        else:
            return mid

    async def update_follower_prices(self, ask: Decimal, bid: Decimal) -> None:
        async with stopwatches.follower.stopwatch(
            self.clear_follower_prices, sleep_seconds.clear_follower_prices
        ):
            self.follower.ask = ask
            self.follower.bid = bid

        await asyncio.sleep(0)

    def clear_follower_prices(self):
        self.follower.ask = None
        self.follower.bid = None
