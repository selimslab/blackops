import asyncio
import collections
import decimal
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.environment import sleep_seconds

from .models import MarketPrices, Window, stopwatches


@dataclass
class PriceAPI:
    bridge: Optional[Decimal] = None
    follower: MarketPrices = field(default_factory=MarketPrices)
    precision_ask: Decimal = Decimal(0)
    precision_bid: Decimal = Decimal(0)

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

    def get_precise_price(self, price: Decimal, reference: Decimal) -> Decimal:
        return price.quantize(reference, rounding=decimal.ROUND_DOWN)

    async def update_follower_prices(self, ask: Decimal, bid: Decimal) -> None:
        async with stopwatches.follower.stopwatch(
            self.clear_follower_prices, sleep_seconds.clear_follower_prices
        ):
            self.follower.ask = ask
            self.follower.bid = bid
            if not self.precision_ask:
                self.precision_ask = ask
                self.precision_bid = bid

        await asyncio.sleep(0)

    def clear_follower_prices(self):
        self.follower.ask = None
        self.follower.bid = None
