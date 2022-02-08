import asyncio
import decimal
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

from .config import settings


@dataclass
class NoBuy:
    max_spread: int = 0
    slope: int = 0


@dataclass
class Stats:
    leader_proc: int = 0
    follower_proc: int = 0
    no_buy: NoBuy = field(default_factory=NoBuy)


@dataclass
class Theo:
    sell: Decimal = Decimal(0)
    mid: Decimal = Decimal(0)
    usdt: Decimal = Decimal(0)
    buy: Decimal = Decimal(0)


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
        self.base_step_qty = round_decimal_half_up(settings.quote_step_qty / price)

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
            if not self.leader_pub.book.mid or self.leader_pub.book.mid == pre:
                await asyncio.sleep(0)
                continue

            try:
                self.set_taker_mids()
                await self.should_sell()

                pre = copy(self.leader_pub.book.mid)
                self.stats.leader_proc += 1

                await asyncio.sleep(0)

            except Exception as e:
                logger.error(e)

    async def poll_follower_pub(self):
        while True:
            if self.stats.follower_proc < self.follower_pub.book.seen:
                await self.should_sell()
                await self.should_buy()
                self.stats.follower_proc = copy(self.follower_pub.book.seen)

            await asyncio.sleep(0)

    def set_taker_mids(self):
        self.taker.usdt = self.leader_pub.book.mid

        if not self.bridge_pub or not self.bridge_pub.book.mid:
            raise Exception("No bridge mid")

        self.taker.mid = self.leader_pub.book.mid * self.bridge_pub.book.mid
        if not self.base_step_qty:
            self.set_base_step_qty(self.taker.mid)

    # SELL
    async def should_sell(self):
        # wait for the bid and base_step_qty to be set
        if not self.follower_pub.book.bid or not self.base_step_qty:
            return

        current_step = self.get_current_step()

        # sell 5 bps more than mid,
        # sell lower as you have more position
        price_coeff = (
            Decimal(1)
            + settings.unit_signal_bps.sell
            - current_step * settings.unit_signal_bps.step
        )

        # if slope down, sell even lower
        if self.leader_pub.slope.risk_level:
            price_coeff -= (
                settings.unit_signal_bps.slope_risk * self.leader_pub.slope.risk_level
            )

        self.taker.sell = self.taker.mid * price_coeff

        price = self.taker.sell.quantize(self.follower_pub.book.bid, decimal.ROUND_DOWN)

        # do not sell if bid is too low
        if self.follower_pub.book.bid < price:
            return

        qty = self.get_sell_qty()

        if not self.order_api.can_sell(price, qty):
            return

        await self.order_api.send_order(OrderType.SELL, price, qty)
        return True

    def get_sell_qty(self):
        qty: Decimal = self.base_step_qty * settings.sell_step

        if qty > self.pair.base.free:
            qty = round_decimal_floor(self.pair.base.free)

        return int(qty)

    # BUY
    async def should_buy(self):
        # wait for the ask and base_step_qty to be set
        if not self.follower_pub.book.ask or not self.base_step_qty:
            return

        # do not buy if spread unhealthy
        if self.leader_pub.spread_bps > settings.max_spread_bps:
            self.stats.no_buy.max_spread += 1
            return

        # dont buy if slope is not clearly up
        if not self.leader_pub.slope.up:
            self.stats.no_buy.slope += 1
            return

        price = self.taker.buy.quantize(self.follower_pub.book.ask, decimal.ROUND_DOWN)

        current_step = self.get_current_step()

        # mid - 15bps - step*1bps
        # seek to buy lower as you buy
        price_coeff = (
            Decimal(1)
            - settings.unit_signal_bps.buy
            - current_step * settings.unit_signal_bps.step
        )

        self.taker.buy = self.taker.mid * price_coeff

        # do not waste orders if ask is too high
        if self.follower_pub.book.ask > price:
            return

        # we could add micro ma
        # if not self.leader_pub.micro_ma_ok:
        #     self.stats.no_buy.micro_ma += 1
        #     return

        qty = self.get_buy_qty(current_step)

        if not qty:
            return

        if not self.order_api.can_buy(price, qty):
            return

        await self.order_api.send_order(OrderType.BUY, price, qty)

    def get_current_step(self):
        return self.pair.base.total_balance / self.base_step_qty

    def get_buy_qty(self, current_step):

        remaining_step = settings.max_step - current_step

        if remaining_step < 1:
            return

        unit_signal = settings.unit_signal_bps.buy * self.taker.mid
        signal = (self.taker.mid - self.follower_pub.book.ask) / unit_signal
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
            "leader": asdict(self.leader_pub.book),
            "follower": asdict(self.follower_pub.book),
            "taker": asdict(self.taker),
            "stats": asdict(self.stats),
            "order": asdict(self.order_api.stats),
            "open fresh": self.order_api.open_orders_fresh,
            "slope": asdict(self.leader_pub.slope),
        }
