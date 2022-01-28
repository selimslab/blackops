import asyncio
import collections
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


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BinancePub
    follower_pub: BTPub
    balance_pub: BalancePub
    bridge_pub: Optional[BTPub] = None

    base_step_qty: Optional[Decimal] = None

    sell_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
    )

    buy_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
    )

    bn_mids: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
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
            self.consume_leader_pub(),
            self.check_follower_update(),
            self.trigger_decide(),
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
    async def consume_leader_pub(self) -> None:
        pre = None
        while True:
            if self.leader_pub.mid and self.leader_pub.mid != pre:

                self.taker.usdt = self.leader_pub.mid

                if self.bridge_pub and self.bridge_pub.mid:
                    self.taker.mid = self.leader_pub.mid * self.bridge_pub.mid
                else:
                    return

                self.add_signals()
                pre = self.leader_pub.mid
                self.stats.leader_seen += 1
            await asyncio.sleep(0)

    def add_signals(self):
        self.add_sell_signal()
        self.add_buy_signal()

    async def trigger_decide(self) -> None:
        proc = 0
        while True:
            seen = self.stats.leader_seen + self.stats.follower_seen
            if seen > proc:
                proc = seen
                await self.decide()
            await asyncio.sleep(0)

    def add_sell_signal(self):
        """
        Not even looking at bridge
        """
        mid = self.taker.usdt
        if not mid:
            return

        if not self.base_step_qty:
            self.set_base_step_qty(mid)

        if len(self.bn_mids) < 3:
            self.bn_mids.append(mid)
            return

        median_of_last_n_bids = statistics.median(self.bn_mids)
        self.bn_mids.append(mid)
        unit_signal = self.config.unit_signal_bps.sell * median_of_last_n_bids
        # sell if median_of_last_n_bids > 1bips of mid
        signal = (median_of_last_n_bids - mid) / unit_signal
        self.sell_signals.append(signal)

    def add_buy_signal(self):
        if self.taker.mid and self.follower_pub.ask:
            unit_signal = self.config.unit_signal_bps.buy * self.taker.mid
            signal = (self.taker.mid - self.follower_pub.ask) / unit_signal
            self.buy_signals.append(signal)

    # FOLLOWER
    async def check_follower_update(self):
        # loop = asyncio.get_event_loop()
        while True:
            if (
                self.follower_pub.bid != self.market.bid
                or self.follower_pub.ask != self.market.ask
            ):

                self.market.ask = self.follower_pub.ask
                self.market.bid = self.follower_pub.bid
                self.add_buy_signal()
                self.stats.follower_seen += 1

            await asyncio.sleep(0)

    # DECIDE
    async def decide(self):
        if self.decide_lock.locked():
            self.stats.decision_locked += 1
            return

        if not self.leader_pub.mid:
            self.stats.missing_data += 1
            return

        async with self.decide_lock:
            self.stats.decisions += 1

            await self.check_sell()
            await self.check_buy()

    async def check_sell(self):
        res = self.should_sell()
        if res:
            price, qty, decision_input = res
            await self.order_api.send_order(OrderType.SELL, price, qty, decision_input)
            self.stats.sell_tried += 1

    async def check_buy(self):
        res = self.should_buy()
        if res:
            price, qty, decision_input = res
            await self.order_api.send_order(OrderType.BUY, price, qty, decision_input)
            self.stats.buy_tried += 1

    def get_precise_price(
        self, price: Decimal, reference: Decimal, rounding
    ) -> Decimal:
        return price.quantize(reference, rounding=rounding)

    def should_sell(self):
        if not self.sell_signals:
            return

        self.taker.sell = self.taker.mid * (
            Decimal(1) + self.config.unit_signal_bps.sell
        )

        self.signals.sell = max(self.sell_signals)

        if (
            self.signals.sell > 1
            and self.follower_pub.bid
            and self.taker.mid <= self.follower_pub.bid
        ):

            price = self.get_precise_price(
                self.taker.sell, self.follower_pub.bid, decimal.ROUND_HALF_DOWN
            )
            price = n_bps_lower(price, Decimal(3))

            qty = self.base_step_qty * self.signals.sell
            if qty > self.pair.base.free:
                qty = round_decimal_floor(self.pair.base.free)

            qty = int(qty)

            if not self.order_api.can_sell(price, qty):
                self.stats.sell_not_needed += 1
                return

            decision_input = OrderDecisionInput(
                market=copy(self.market),
                taker=copy(self.taker),
            )
            return price, qty, decision_input

    def should_buy(self):
        if not self.buy_signals or not self.follower_pub.ask:
            return

        self.signals.buy = statistics.mean(self.buy_signals)

        self.taker.buy = self.taker.mid * (Decimal(1) - self.config.unit_signal_bps.buy)

        if self.signals.buy > 1 and self.buy_signals[-1] > 1:

            price = self.get_precise_price(
                self.taker.buy, self.follower_pub.ask, decimal.ROUND_HALF_DOWN
            )
            price = n_bps_higher(price, Decimal(2))

            qty = int(self.base_step_qty)

            current_step = self.pair.base.total_balance / self.base_step_qty
            remaining_step = self.config.max_step - current_step
            if remaining_step < 1:
                qty = int(self.base_step_qty * remaining_step)

            if not self.order_api.can_buy(price, qty):
                self.stats.buy_not_needed += 1
                return None

            decision_input = OrderDecisionInput(
                market=copy(self.market),
                taker=copy(self.taker),
            )
            return price, qty, decision_input

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "pair": self.pair.dict(),
            "mids": list(self.bn_mids),
            "buy signals": list(self.buy_signals),
            "sell signals": list(self.sell_signals),
            "sma signals": asdict(self.signals),
            "prices": {
                "ask": self.follower_pub.ask,
                "bid": self.follower_pub.bid,
                # "mids": list(self.mids_seen),
                # "bids": list(self.bids_seen),
                # "asks": list(self.asks_seen),
                "taker": asdict(self.taker),
                "bn seen": self.leader_pub.books_seen,
                "bt seen": self.follower_pub.books_seen,
                "stats": asdict(self.stats),
            },
            "order": {
                "fresh": self.order_api.open_orders_fresh,
                "stats": asdict(self.order_api.stats),
                "last 3 cancelled": list(
                    asdict(order) for order in self.order_api.last_cancelled
                ),
                "last 3 filled": list(
                    asdict(order) for order in self.order_api.last_filled
                ),
            },
        }
