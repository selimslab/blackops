import asyncio
import decimal
import statistics
from copy import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from src.domain import BPS, OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import periodic
from src.pubsub.pubs import BalancePub, BinancePub, BTPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import BookTop, Theo


@dataclass
class NoBuy:
    max_spread: int = 0
    klines: int = 0
    qty: int = 0


@dataclass
class NoSell:
    qty: int = 0


@dataclass
class Stats:
    leader_seen: int = 0
    follower_seen: int = 0

    sell_tried: int = 0
    buy_tried: int = 0

    no_buy: NoBuy = field(default_factory=NoBuy)
    no_sell: NoSell = field(default_factory=NoSell)


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BinancePub
    follower_pub: BTPub
    balance_pub: BalancePub
    bridge_pub: Optional[BTPub] = None

    base_step_qty: Optional[Decimal] = None

    start_time: datetime = field(default_factory=lambda: datetime.now())

    stats: Stats = field(default_factory=Stats)

    taker: Theo = field(default_factory=Theo)

    market: BookTop = field(default_factory=BookTop)

    def __post_init__(self) -> None:
        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)
        self.pair.base = self.balance_pub.get_asset(self.config.input.base)
        self.pair.quote = self.balance_pub.get_asset(self.config.input.quote)

        self.order_api = OrderApi(
            config=self.config,
            pair=self.pair,
            exchange=self.follower_pub.api_client,
        )

    def set_base_step_qty(self, price: Decimal) -> None:
        self.base_step_qty = round_decimal_half_up(self.config.quote_step_qty / price)

    async def run(self) -> None:
        logger.info(f"Starting {self.config.sha}..")
        await self.run_streams()

    async def run_streams(self) -> None:
        aws: Any = [
            self.poll_leader_pub(),
            self.poll_follower_pub(),
            periodic(
                self.order_api.refresh_open_orders,
                sleep_seconds.refresh_open_orders,
            ),
            periodic(
                self.order_api.clear_orders_in_last_second,
                0.95,
            ),
        ]

        await asyncio.gather(*aws)

    # LEADER
    async def poll_leader_pub(self) -> None:
        pre = None
        while True:
            if not self.leader_pub.mid or self.leader_pub.mid == pre:
                await asyncio.sleep(0)
                continue

            try:
                self.set_taker_mids()
                await self.should_sell()

                pre = copy(self.leader_pub.mid)
                self.stats.leader_seen += 1

                await asyncio.sleep(0)

            except Exception as e:
                logger.error(e)
                pass

    async def poll_follower_pub(self):
        while True:
            if self.stats.follower_seen < self.follower_pub.books_seen:
                await self.should_sell()
                await self.should_buy()
                self.stats.follower_seen = copy(self.follower_pub.books_seen)

            await asyncio.sleep(0)

    def set_taker_mids(self):
        self.taker.usdt = self.leader_pub.mid

        if not self.bridge_pub or not self.bridge_pub.mid:
            raise Exception("No bridge mid")

        self.taker.mid = self.leader_pub.mid * self.bridge_pub.mid
        if not self.base_step_qty:
            self.set_base_step_qty(self.taker.mid)

    # SELL
    async def should_sell(self):

        if not self.follower_pub.bid or not self.base_step_qty:
            return

        current_step = self.get_current_step()
        price_coeff = (
            Decimal(1)
            + self.config.unit_signal_bps.sell
            - current_step * self.config.unit_signal_bps.step
        )
        if not self.leader_pub.is_slope_up:
            price_coeff -= self.config.unit_signal_bps.slope_risk

        # -1bps - 4*1bps = -5bps
        # with slope risk, -10 = -15bps
        self.taker.sell = self.taker.mid * price_coeff

        price = self.taker.sell.quantize(self.follower_pub.bid, decimal.ROUND_DOWN)

        if self.follower_pub.bid < price:
            return

        qty = self.get_sell_qty()

        if not self.order_api.can_sell(price, qty):
            self.stats.no_sell.qty += 1
            return

        await self.order_api.send_order(OrderType.SELL, price, qty)
        self.stats.sell_tried += 1
        return True

    def get_sell_qty(self):
        qty: Decimal = self.base_step_qty * self.config.sell_step

        if qty > self.pair.base.free:
            qty = round_decimal_floor(self.pair.base.free)

        return int(qty)

    # BUY
    async def should_buy(self):
        if not self.follower_pub.ask or not self.base_step_qty:
            return

        price = self.taker.buy.quantize(self.follower_pub.ask, decimal.ROUND_DOWN)

        current_step = self.get_current_step()
        # -15bps - 4*1bps = -19bps
        price_coeff = (
            Decimal(1)
            - self.config.unit_signal_bps.buy
            - current_step * self.config.unit_signal_bps.step
        )
        self.taker.buy = self.taker.mid * price_coeff

        if self.follower_pub.ask > price:
            return

        if self.leader_pub.spread_bps > self.config.max_spread_bps:
            self.stats.no_buy.max_spread += 1
            return

        if self.leader_pub.is_slope_up:
            self.stats.no_buy.klines += 1
            return

        qty = self.get_buy_qty(current_step)

        if not qty:
            self.stats.no_buy.qty += 1
            return

        if not self.order_api.can_buy(price, qty):
            self.stats.no_buy.qty += 1
            return None

        await self.order_api.send_order(OrderType.BUY, price, qty)
        self.stats.buy_tried += 1

    def get_current_step(self):
        return self.pair.base.total_balance / self.base_step_qty

    def get_buy_qty(self, current_step):

        remaining_step = self.config.max_step - current_step

        if remaining_step < 1:
            return

        unit_signal = self.config.unit_signal_bps.buy * self.taker.mid
        signal = (self.taker.mid - self.follower_pub.ask) / unit_signal
        signal = min(signal, remaining_step)
        qty = self.base_step_qty * signal

        return int(qty)

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "pair": self.pair.dict(),
            "base_step_qty": self.base_step_qty,
            "slope_up": self.leader_pub.is_slope_up,
            "prices": {
                "ask": self.follower_pub.ask,
                "bid": self.follower_pub.bid,
                "taker": asdict(self.taker),
                "bn ask": self.leader_pub.ask,
                "bn bid": self.leader_pub.bid,
                "bn seen": self.leader_pub.books_seen,
                "bt seen": self.follower_pub.books_seen,
                "stats": asdict(self.stats),
            },
            "order": {
                "fresh": self.order_api.open_orders_fresh,
                "stats": asdict(self.order_api.stats),
            },
        }
