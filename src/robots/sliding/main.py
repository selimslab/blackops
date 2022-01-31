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
    dont_buy_max_spread_bps: int = 0
    ma5_dont_buy: int = 0


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

    # single_bt_price_buy_signals: list = field(default_factory=list)

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

                if not self.base_step_qty:
                    self.set_base_step_qty(self.taker.mid)

                self.add_sell_signal()
                self.add_buy_signal()

                pre = self.leader_pub.mid
                self.stats.leader_seen += 1
            await asyncio.sleep(0)

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
        usdt_mid = self.taker.usdt
        if not usdt_mid:
            return

        if len(self.bn_mids) < 3:
            self.bn_mids.append(usdt_mid)
            return

        median_of_last_n_bids = statistics.median(self.bn_mids)
        self.bn_mids.append(usdt_mid)
        unit_signal = self.config.unit_signal_bps.sell * median_of_last_n_bids
        # sell if median_of_last_n_bids > 1bips of mid
        signal = (median_of_last_n_bids - usdt_mid) / unit_signal
        self.sell_signals.append(signal)

    def get_hold_risk(self):
        current_step = self.pair.base.total_balance / self.base_step_qty
        hold_risk = Decimal(1) + current_step * self.config.unit_signal_bps.hold
        return hold_risk

    def add_buy_signal(self):
        if self.taker.mid and self.follower_pub.ask:
            hold_risk = self.get_hold_risk()
            unit_signal = self.config.unit_signal_bps.buy * self.taker.mid
            signal = (self.taker.mid - self.follower_pub.ask * hold_risk) / unit_signal
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

        if not self.leader_pub.mid or not self.follower_pub.bid:
            self.stats.missing_data += 1
            return

        async with self.decide_lock:
            self.stats.decisions += 1

            sell = await self.should_sell()
            if sell:
                return
            await self.should_buy()

    async def should_sell(self):
        res = self.get_sell_order()
        if res:
            price, qty, decision_input = res
            await self.order_api.send_order(OrderType.SELL, price, qty, decision_input)
            self.stats.sell_tried += 1
            return True

    async def should_buy(self):
        res = self.get_buy_order()
        if res:
            price, qty, decision_input = res
            await self.order_api.send_order(OrderType.BUY, price, qty, decision_input)
            self.stats.buy_tried += 1

    def get_precise_price(
        self, price: Decimal, reference: Decimal, rounding
    ) -> Decimal:
        return price.quantize(reference, rounding=rounding)

    def get_sell_order(self):
        if not self.sell_signals:
            return

        self.taker.sell = self.taker.mid * (
            Decimal(1) + self.config.unit_signal_bps.sell
        )

        self.signals.sell = max(self.sell_signals)
        hold_risk = self.get_hold_risk()

        if (
            self.signals.sell > 1
            and self.follower_pub.bid
            and self.taker.mid <= (self.follower_pub.bid) * hold_risk
        ):

            price = self.get_precise_price(
                self.taker.sell, self.follower_pub.bid, decimal.ROUND_HALF_DOWN
            )
            price = n_bps_lower(price, Decimal(4))

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

    def get_buy_order(self):
        if not self.buy_signals or not self.follower_pub.ask:
            return

        self.signals.buy = statistics.mean(self.buy_signals)

        self.taker.buy = self.taker.mid * (Decimal(1) - self.config.unit_signal_bps.buy)

        if self.signals.buy > 1 and self.buy_signals[-1] > 1:

            if self.leader_pub.spread_bps > self.config.max_spread_bps:
                self.stats.dont_buy_max_spread_bps += 1
                return

            if not self.leader_pub.is_klines_ok:
                self.stats.ma5_dont_buy += 1
                return

            price = self.get_precise_price(
                self.taker.buy, self.follower_pub.ask, decimal.ROUND_HALF_DOWN
            )

            qty = self.base_step_qty

            current_step = self.pair.base.total_balance / self.base_step_qty
            remaining_step = self.config.max_step - current_step
            if remaining_step < 1:
                qty = remaining_step * self.base_step_qty

            qty = int(qty)

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
            # "config": self.config.dict(),
            "base_step_qty": self.base_step_qty,
            # "mids": list(self.bn_mids),
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
