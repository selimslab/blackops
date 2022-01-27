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
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import periodic
from src.proc import thread_pool_executor
from src.pubsub.pubs import BalancePub, BinancePub, BTPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi, OrderDecisionInput
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import BookTop, Signals, Theo


@dataclass
class Stats:
    pass


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BinancePub
    follower_pub: BTPub
    balance_pub: BalancePub
    bridge_pub: Optional[BTPub] = None

    base_step_qty: Optional[Decimal] = None

    leader_sell_signals: list = field(default_factory=list)
    leader_buy_signals: list = field(default_factory=list)

    follower_sell_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=2)
    )

    follower_buy_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=2)
    )

    signals: Signals = field(default_factory=Signals)

    leader_seen: int = 0
    follower_seen: int = 0

    taker: Theo = field(default_factory=Theo)

    start_time: datetime = field(default_factory=lambda: datetime.now())

    decide_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    market: BookTop = field(default_factory=BookTop)

    # mids_seen: collections.deque = field(
    #     default_factory=lambda: collections.deque(maxlen=12)
    # )
    # bids_seen: collections.deque = field(
    #     default_factory=lambda: collections.deque(maxlen=12)
    # )
    # asks_seen: collections.deque = field(
    #     default_factory=lambda: collections.deque(maxlen=12)
    # )

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
            if self.leader_pub.mid != pre:
                self.consume_leader_book()
                pre = self.leader_pub.mid
                await self.decide()
            await asyncio.sleep(0)

    def consume_leader_book(self) -> None:

        self.taker.usdt = self.leader_pub.mid

        mid = None
        if self.bridge_pub:
            mid = self.leader_pub.mid * self.bridge_pub.mid

        if not mid:
            return

        self.taker.mid = mid

        if not self.base_step_qty:
            self.set_base_step_qty(self.taker.mid)

        self.add_signal(mid)

        self.leader_seen += 1

    def add_signal(self, mid: Decimal):
        bid = self.follower_pub.bid
        if bid:
            unit_signal = self.config.unit_signal_bps.sell * mid
            signal = (bid - mid) / unit_signal
            self.leader_sell_signals.append(signal)

        ask = self.follower_pub.ask
        if ask:
            unit_signal = self.config.unit_signal_bps.buy * mid
            signal = (mid - ask) / unit_signal
            self.leader_buy_signals.append(signal)

    def check_follower_update(self):
        if (
            self.follower_pub.bid != self.market.bid
            or self.follower_pub.ask != self.market.ask
        ):
            self.market.ask = self.follower_pub.ask
            self.market.bid = self.follower_pub.bid
            self.aggregate_signals()
            self.follower_seen += 1

    def aggregate_signals(self):
        if self.leader_buy_signals:
            self.follower_buy_signals.append(statistics.mean(self.leader_buy_signals))
            self.leader_buy_signals = []

        if self.leader_sell_signals:
            self.follower_sell_signals.append(statistics.mean(self.leader_sell_signals))
            self.leader_sell_signals = []

    # async def trigger_decide(self):
    #     while True:
    #         if self.leader_seen % 2 == 0:
    #             # self.aggregate_signals()
    #             await self.decide()
    #         await asyncio.sleep(0)

    # DECIDE
    async def decide(self):
        if self.decide_lock.locked():
            return

        async with self.decide_lock:
            self.check_follower_update()

            res = self.should_sell()
            if res:
                price, qty, decision_input = res

                await self.order_api.send_order(
                    OrderType.SELL, price, qty, decision_input
                )
                return

            res = self.should_buy()
            if res:
                price, qty, decision_input = res
                await self.order_api.send_order(
                    OrderType.BUY, price, qty, decision_input
                )

    def get_precise_price(
        self, price: Decimal, reference: Decimal, rounding
    ) -> Decimal:
        return price.quantize(reference, rounding=rounding)

    def should_sell(self):
        if not self.follower_sell_signals:
            return

        self.signals.sell = statistics.mean(self.follower_sell_signals)

        self.taker.sell = (
            self.leader_pub.mid
            * self.bridge_pub.mid
            * (Decimal(1) + self.config.unit_signal_bps.sell)
        )

        if self.signals.sell > 1 and self.taker.sell <= self.follower_pub.bid:
            price = self.get_precise_price(
                self.taker.sell, self.follower_pub.bid, decimal.ROUND_DOWN
            )
            qty = self.base_step_qty * self.signals.sell
            if qty > self.pair.base.free:
                qty = round_decimal_floor(self.pair.base.free)
            qty = int(qty)

            if not self.order_api.can_sell(price, qty):
                return

            decision_input = OrderDecisionInput(
                market=copy(self.market),
                taker=copy(self.taker),
            )
            return price, qty, decision_input

    def should_buy(self):
        if not self.follower_buy_signals:
            return

        self.signals.buy = statistics.mean(self.follower_buy_signals)

        self.taker.buy = (
            self.leader_pub.mid
            * self.bridge_pub.mid
            * (Decimal(1) - self.config.unit_signal_bps.buy)
        )

        if self.signals.buy > 1 and self.taker.buy >= self.follower_pub.ask:
            price = self.get_precise_price(
                self.taker.buy, self.follower_pub.ask, decimal.ROUND_HALF_UP
            )

            qty = self.base_step_qty * self.signals.buy
            max_buyable = (
                self.config.max_step * self.base_step_qty - self.pair.base.total_balance
            )
            qty = min(qty, max_buyable)
            qty = int(qty)

            if not self.order_api.can_buy(price, qty):
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
            "signals": asdict(self.signals),
            # "buy signals": list(self.follower_buy_signals),
            # "sell signals": list(self.follower_sell_signals),
            "prices": {
                "ask": self.follower_pub.ask,
                "bid": self.follower_pub.bid,
                # "mids": list(self.mids_seen),
                # "bids": list(self.bids_seen),
                # "asks": list(self.asks_seen),
                "taker": asdict(self.taker),
                "bn seen": self.leader_pub.books_seen,
                "bn proc": self.leader_seen,
                "bt seen": self.follower_pub.books_seen,
                "bt proc": self.follower_seen,
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
