import asyncio
import collections
import decimal
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from src.domain import BPS, OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import periodic
from src.proc import process_pool_executor, thread_pool_executor
from src.pubsub import create_binance_consumer_generator, create_bt_consumer_generator
from src.pubsub.pubs import BalancePub, BinancePub, BookPub, BTPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi, OrderDecisionInput
from src.stgs.sliding.config import LeaderFollowerConfig

from .models import BidAsk, PriceWindow


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
        default_factory=lambda: collections.deque(maxlen=3)
    )

    follower_buy_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
    )

    sell_signal: Optional[Decimal] = None
    buy_signal: Optional[Decimal] = None

    start_time: datetime = field(default_factory=lambda: datetime.now())

    leader_prices_processed: int = 0
    follower_prices_processed: int = 0

    taker_prices: PriceWindow = field(default_factory=PriceWindow)
    bridge: Optional[Decimal] = None
    bidask: BidAsk = field(default_factory=BidAsk)

    decide_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

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
            self.consume_follower_pub(),
            periodic(
                self.order_api.refresh_open_orders,
                sleep_seconds.refresh_open_orders,
            ),
            periodic(
                self.order_api.clear_orders_in_last_second,
                0.95,
            ),
        ]

        if self.bridge_pub:
            aws.append(self.consume_bridge_pub())

        await asyncio.gather(*aws)

    # BRIDGE

    async def consume_bridge_pub(self) -> None:
        if not self.bridge_pub:
            raise Exception("no bridge_pub")
        gen = create_bt_consumer_generator(self.bridge_pub)
        async for res in gen:
            if res:
                bid, ask = res
                self.bridge = (bid + ask) / Decimal(2)
            await asyncio.sleep(0)

    # FOLLOWER
    async def consume_follower_pub(self) -> None:
        gen = create_bt_consumer_generator(self.follower_pub)
        loop = asyncio.get_running_loop()

        async for res in gen:
            if res:
                await loop.run_in_executor(
                    thread_pool_executor, self.consume_bt_price, res
                )
            await asyncio.sleep(0)

    def consume_bt_price(self, res):
        bid, ask = res

        if not self.base_step_qty:
            mid = (ask + bid) / Decimal(2)
            self.set_base_step_qty(mid)

        self.bidask.bid = bid
        self.bidask.ask = ask
        if self.leader_buy_signals:
            self.follower_buy_signals.append(statistics.mean(self.leader_buy_signals))
            self.leader_buy_signals = []

        if self.leader_sell_signals:
            self.follower_sell_signals.append(statistics.mean(self.leader_sell_signals))
            self.leader_sell_signals = []

        self.follower_prices_processed += 1

    # LEADER
    async def consume_leader_pub(self) -> None:
        gen = create_binance_consumer_generator(self.leader_pub)
        loop = asyncio.get_running_loop()

        async for mid in gen:
            if mid:
                await loop.run_in_executor(
                    thread_pool_executor, self.consume_leader_book, mid
                )
                await self.decide()
            await asyncio.sleep(0)

    def consume_leader_book(self, mid: Decimal) -> None:
        self.taker_prices.mid = mid

        if self.bridge:
            mid *= self.bridge

        self.taker_prices.bridged_mid = mid

        self.update_signals(mid)

        self.leader_prices_processed += 1

    def update_signals(self, mid: Decimal):
        bid = self.bidask.bid
        if bid:
            unit_signal = self.config.unit_signal_bps.sell * mid
            signal = (bid - mid) / unit_signal
            self.leader_sell_signals.append(signal)
            self.taker_prices.sell = mid + unit_signal

        ask = self.bidask.ask
        if ask:
            unit_signal = self.config.unit_signal_bps.buy * mid
            signal = (mid - ask) / unit_signal
            self.leader_buy_signals.append(signal)
            self.taker_prices.buy = mid - unit_signal

    async def decide(self):

        if self.decide_lock.locked():
            return

        if not self.base_step_qty:
            return

        if not self.follower_sell_signals:
            return

        loop = asyncio.get_running_loop()

        async with self.decide_lock:
            res = await loop.run_in_executor(thread_pool_executor, self.should_sell)
            if res:
                price, qty = res
                decision_input = OrderDecisionInput(
                    signal=self.sell_signal,
                    mid=self.taker_prices.bridged_mid,
                    ask=self.bidask.ask,
                    bid=self.bidask.bid,
                    theo_buy=self.taker_prices.buy,
                    theo_sell=self.taker_prices.sell,
                )
                await self.order_api.send_order(
                    OrderType.SELL, price, qty, decision_input
                )
                return

            res = await loop.run_in_executor(thread_pool_executor, self.should_buy)
            if res:
                price, qty = res
                decision_input = OrderDecisionInput(
                    signal=self.buy_signal,
                    mid=self.taker_prices.bridged_mid,
                    ask=self.bidask.ask,
                    bid=self.bidask.bid,
                    theo_buy=self.taker_prices.buy,
                    theo_sell=self.taker_prices.sell,
                )
                await self.order_api.send_order(
                    OrderType.BUY, price, qty, decision_input
                )

    def get_precise_price(
        self, price: Decimal, reference: Decimal, rounding
    ) -> Decimal:
        return price.quantize(reference, rounding=rounding)

    def should_sell(self):
        mean_signal = statistics.mean(self.follower_sell_signals)
        self.sell_signal = mean_signal
        last_signal = self.follower_sell_signals[-1]

        if mean_signal > 1 and last_signal > 1:
            price = self.get_precise_price(
                self.taker_prices.sell, self.bidask.bid, decimal.ROUND_DOWN
            )
            qty = self.base_step_qty * mean_signal
            if qty > self.pair.base.free:
                qty = round_decimal_floor(self.pair.base.free)
            qty = int(qty)

            if not self.order_api.can_sell(price, qty):
                return

            return price, qty

    def should_buy(self):
        mean_signal = statistics.mean(self.follower_buy_signals)
        self.buy_signal = mean_signal
        last_signal = self.follower_buy_signals[-1]

        if mean_signal > 1 and last_signal > 1:
            price = self.get_precise_price(
                self.taker_prices.buy, self.bidask.ask, decimal.ROUND_HALF_UP
            )

            qty = self.base_step_qty * mean_signal
            max_buyable = (
                self.config.max_step * self.base_step_qty - self.pair.base.total_balance
            )
            qty = min(qty, max_buyable)
            qty = int(qty)

            if not self.order_api.can_buy(price, qty):
                return None

            return price, qty

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "pair": self.pair.dict(),
            "buy signal": self.buy_signal,
            "sell signal": self.sell_signal,
            "buy signals": list(self.follower_buy_signals),
            "sell signals": list(self.follower_sell_signals),
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
            "prices": {
                "market": asdict(self.bidask),
                "bridge": self.bridge,
                "taker": asdict(self.taker_prices),
                "bn seen": self.leader_pub.books_seen,
                "bn proc": self.leader_prices_processed,
                "bt seen": self.follower_pub.books_seen,
                "bt proc": self.follower_prices_processed,
            },
        }
