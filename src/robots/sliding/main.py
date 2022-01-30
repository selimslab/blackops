import asyncio
import collections
import decimal
import statistics
from copy import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import _Step
from typing import Any, Optional

from src.domain import BPS, OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import n_bps_higher, round_decimal_floor, round_decimal_half_up
from src.numberops.main import n_bps_lower
from src.periodic import periodic
from src.proc import thread_pool_executor
from src.pubsub.pubs import BalancePub, BinancePub, BTPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi, OrderDecisionInput
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import BookTop, Signals, Theo


@dataclass
class Stats:
    leader_seen: int = 0
    follower_seen: int = 0
    decisions: int = 0
    decision_locked: int = 0
    missing_data: int = 0
    sell_tried: int = 0
    buy_tried: int = 0
    buy_not_needed: int = 0
    sell_not_needed: int = 0

    cant_sell: int = 0
    cant_buy: int = 0

    dont_buy_max_spread_bps: int = 0
    ma5_dont_buy: int = 0
    bn_mid_too_high_to_sell: int = 0


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BinancePub
    follower_pub: BTPub
    balance_pub: BalancePub
    bridge_pub: Optional[BTPub] = None

    base_step_qty: Optional[Decimal] = None

    sell_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=10)
    )

    buy_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=5)
    )

    bn_usdt_mids: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=5)
    )

    signals: Signals = field(default_factory=Signals)

    taker: Theo = field(default_factory=Theo)

    start_time: datetime = field(default_factory=lambda: datetime.now())

    decide_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    market: BookTop = field(default_factory=BookTop)

    stats: Stats = field(default_factory=Stats)

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

    def set_taker_mids(self):
        self.taker.usdt = self.leader_pub.usdt_mid

        if not self.bridge_pub or not self.bridge_pub.mid:
            raise Exception("No bridge mid")

        self.taker.mid = self.leader_pub.usdt_mid * self.bridge_pub.mid
        self.taker.std = self.leader_pub.std * self.bridge_pub.mid

    # LEADER
    async def poll_leader_pub(self) -> None:
        pre = None
        while True:
            if not self.leader_pub.usdt_mid or self.leader_pub.usdt_mid == pre:
                await asyncio.sleep(0)
                continue

            try:
                await self.consume_leader_pub()

                pre = self.leader_pub.usdt_mid
                self.stats.leader_seen += 1

                await asyncio.sleep(0)

            except Exception as e:
                pass

    async def consume_leader_pub(self) -> None:
        self.set_taker_mids()

        if not self.base_step_qty:
            self.set_base_step_qty(self.taker.mid)

        await self.add_sell_signal()
        await self.add_buy_signal()

    async def add_sell_signal(self):
        # try sell if bn mid drops 1.1 std
        signal = (
            (self.leader_pub.mean - self.leader_pub.usdt_mid)
            / self.leader_pub.std
            * Decimal("1.1")
        )
        self.sell_signals.append(signal)
        if signal > 1:
            await self.decide()

    async def add_buy_signal(self):
        """
        We can directly try sell yet this is to remember and keep trying if we don't sell at first
        """
        if self.taker.mid and self.follower_pub.ask:
            unit_signal = self.config.unit_signal_bps.buy * self.taker.mid
            signal = (
                self.taker.mid - self.taker.std - self.follower_pub.ask
            ) / unit_signal
            self.buy_signals.append(signal)
            if signal > 1:
                await self.decide()

    # DECIDE
    async def decide(self):
        if self.decide_lock.locked():
            self.stats.decision_locked += 1
            return

        if not self.leader_pub.usdt_mid or not self.follower_pub.bid:
            self.stats.missing_data += 1
            return

        async with self.decide_lock:
            self.stats.decisions += 1

            sell_tried = await self.should_sell()
            if sell_tried:
                return
            await self.should_buy()

    def get_precise_price(
        self, price: Decimal, reference: Decimal, rounding
    ) -> Decimal:
        return price.quantize(reference, rounding=rounding)

    # SELL
    def can_sell(self):
        if not self.sell_signals:
            return False

        self.signals.sell = max(self.sell_signals)

        if self.signals.sell < 1:
            self.stats.sell_not_needed += 1
            return False

        if (
            self.follower_pub.bid
            and self.taker.mid > self.follower_pub.bid + 2 * self.taker.std
        ):
            self.stats.bn_mid_too_high_to_sell += 1
            return False

        return True

    async def should_sell(self):

        if not self.can_sell():
            return

        price = self.get_sell_price()
        qty = self.get_sell_qty()

        if not self.order_api.can_sell(price, qty):
            self.stats.cant_sell += 1
            return

        # decision_input = OrderDecisionInput(
        #     market=copy(self.market),
        #     taker=copy(self.taker),
        # )

        await self.order_api.send_order(OrderType.SELL, price, qty)
        self.stats.sell_tried += 1
        return True

    def get_sell_price(self):
        price = self.get_precise_price(
            self.taker.mid, self.follower_pub.bid, decimal.ROUND_HALF_DOWN
        )
        price = n_bps_lower(price, Decimal(4))

        return price

    def get_sell_qty(self):
        qty = self.base_step_qty * self.signals.sell * self.config.step_per_signal

        if qty > self.pair.base.free:
            qty = round_decimal_floor(self.pair.base.free)

        return int(qty)

    # BUY
    def get_buy_qty(self):
        qty = self.base_step_qty

        current_step = self.pair.base.total_balance / self.base_step_qty
        remaining_step = self.config.max_step - current_step
        if remaining_step < 1:
            return

        return int(qty)

    def get_buy_price(self):
        return self.get_precise_price(
            self.taker.buy, self.follower_pub.ask, decimal.ROUND_HALF_DOWN
        )

    def can_buy(self):
        if not self.buy_signals or not self.follower_pub.ask:
            return False

        self.signals.buy = statistics.mean(self.buy_signals)

        self.taker.buy = self.taker.mid * (Decimal(1) - self.config.unit_signal_bps.buy)

        if self.signals.buy < 1 or self.buy_signals[-1] < 1:
            self.stats.buy_not_needed += 1
            return False

        if self.leader_pub.spread_bps > self.config.max_spread_bps:
            self.stats.dont_buy_max_spread_bps += 1
            return False

        if self.leader_pub.ma5 and self.leader_pub.usdt_mid < self.leader_pub.ma5:
            self.stats.ma5_dont_buy += 1
            return False

        return True

    async def should_buy(self):
        if not self.can_buy():
            return

        price = self.get_buy_price()

        qty = self.get_buy_qty()

        if not (price and qty):
            self.stats.cant_buy += 1
            return

        if not self.order_api.can_buy(price, qty):
            self.stats.cant_buy += 1
            return None

        await self.order_api.send_order(OrderType.BUY, price, qty)
        self.stats.buy_tried += 1

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "pair": self.pair.dict(),
            "config": self.config.dict(),
            "base_step_qty": self.base_step_qty,
            # "mids": list(self.bn_usdt_mids),
            # "buy signals": list(self.buy_signals),
            # "sell signals": list(self.sell_signals),
            "signals": asdict(self.signals),
            "ma5": self.leader_pub.ma5,
            "prices": {
                "ask": self.follower_pub.ask,
                "bid": self.follower_pub.bid,
                # "mids": list(self.mids_seen),
                # "bids": list(self.bids_seen),
                # "asks": list(self.asks_seen),
                "taker": asdict(self.taker),
                "bn ask": self.leader_pub.ask,
                "bn spread": self.leader_pub.spread_bps,
                "bn bid": self.leader_pub.bid,
                "bn seen": self.leader_pub.books_seen,
                "bt seen": self.follower_pub.books_seen,
                "stats": asdict(self.stats),
            },
            "order": {
                "fresh": self.order_api.open_orders_fresh,
                "stats": asdict(self.order_api.stats),
                # "last 3 cancelled": list(
                #     asdict(order) for order in self.order_api.last_cancelled
                # ),
                # "last 3 filled": list(
                #     asdict(order) for order in self.order_api.last_filled
                # ),
            },
        }
