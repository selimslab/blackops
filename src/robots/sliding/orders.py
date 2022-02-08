import asyncio
import collections
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.locks import Locks
from src.monitoring import logger
from src.stgs import LeaderFollowerConfig

from .config import settings


@dataclass
class DeliveryStats:
    delivered: int = 0
    cancelled: int = 0
    filled: int = 0


@dataclass
class BuyStats(DeliveryStats):
    pass


@dataclass
class SellStats(DeliveryStats):
    pass


@dataclass
class FailCounts:
    open_orders: int = 0
    hit_order_limit = 0
    parent: int = 0
    bad_response: int = 0
    self_lock: int = 0


@dataclass
class OrderStats:

    buy_stats: BuyStats = field(default_factory=BuyStats)
    sell_stats: SellStats = field(default_factory=SellStats)

    fail_counts: FailCounts = field(default_factory=FailCounts)


@dataclass
class Order:
    order_id: OrderId
    symbol: str
    side: str
    price: Decimal
    qty: Decimal


@dataclass
class OrderApi:
    config: LeaderFollowerConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    open_orders: collections.deque = field(default_factory=collections.deque)
    cancelled_orders: dict = field(default_factory=dict)
    # probably_filled: list = field(default_factory=list)

    last_cancelled: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
    )
    last_filled: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=3)
    )

    stats: OrderStats = field(default_factory=OrderStats)

    locks: Locks = field(default_factory=Locks)
    open_orders_fresh: bool = True

    orders_in_last_second: int = 0
    max_orders_per_second: int = 3

    async def clear_orders_in_last_second(self):
        self.orders_in_last_second = 0

    async def cancel_open_orders(self) -> None:
        try:
            if not self.open_orders:
                return None

            if self.locks.cancel.locked():
                return None

            async with self.locks.cancel:
                while self.open_orders:
                    order: Order = self.open_orders[0]
                    await self.cancel_order(order)
                    self.open_orders.popleft()

                if self.open_orders_fresh:
                    self.cancelled_orders = {}

        except Exception as e:
            msg = f"cancel_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def cancel_order(self, order: Order) -> None:
        if order.order_id in self.cancelled_orders:
            return

        await self.poll_for_lock(self.exchange.locks.cancel)

        ok = await self.exchange.cancel_order(order.order_id)

        if ok:
            self.cancel_successful(order)
        else:
            self.cancel_failed(order)

    def cancel_successful(self, order: Order) -> None:
        self.cancelled_orders[order.order_id] = order
        self.last_cancelled.append(order)
        # logger.info(f"cancelled: {asdict(order)}")

        if order.side == OrderType.BUY:
            # self.pair.base.free -= order.qty
            self.stats.buy_stats.cancelled += 1
        else:
            # self.pair.base.free += order.qty
            self.stats.sell_stats.cancelled += 1

    def cancel_failed(self, order: Order) -> None:
        # couldn't cancel but maybe filled
        self.open_orders_fresh = False
        if order.side == OrderType.BUY:
            self.stats.buy_stats.filled += 1
        else:
            self.stats.sell_stats.filled += 1

        self.last_filled.append(order)

    async def poll_for_lock(self, lock):
        while lock.locked():
            await asyncio.sleep(sleep_seconds.poll_for_lock)

    async def refresh_open_orders(self) -> None:
        if self.open_orders_fresh:
            return None

        if self.locks.read.locked():
            return None

        async with self.locks.read:
            await self.poll_for_lock(self.exchange.locks.read)

            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            # loop = asyncio.get_event_loop()
            if res:
                # loop.run_in_executor(thread_pool_executor, self.get_and_refresh, res)
                self.get_and_refresh(res)

        await self.cancel_open_orders()

    def get_and_refresh(self, res):
        orderlist = self.exchange.get_sorted_order_list(res)
        self.refresh_open_order_successful(orderlist)

    def refresh_open_order_successful(self, orderlist: list) -> None:
        orders = [
            Order(
                order_id=order_dict.get("id"),
                price=Decimal(order_dict["price"]),
                qty=Decimal(order_dict.get("leftAmount", 0)),
                symbol=order_dict.get("pairSymbol"),
                side=order_dict.get("type"),
            )
            for order_dict in orderlist
        ]

        for order in orders:
            if order.order_id not in self.cancelled_orders:
                self.open_orders.append(order)

        self.open_orders_fresh = True
        self.cancelled_orders = {}

    def can_sell(self, price, qty) -> bool:
        # do we have enough to sell, and is it too little to sell=
        return self.pair.base.free >= qty and qty * price >= settings.min_sell_qty

    def can_buy(self, price, qty) -> bool:
        # Do we have enough money and is it too little to buy?
        return (
            bool(self.pair.quote.free)
            and self.pair.quote.free >= price * qty > settings.min_buy_qty
        )

    def can_order(self, side: OrderType, price: Decimal, qty: int) -> bool:

        if self.orders_in_last_second >= self.max_orders_per_second:
            self.stats.fail_counts.hit_order_limit += 1
            return False

        if len(self.open_orders) > 0 or not self.open_orders_fresh:
            self.stats.fail_counts.open_orders += 1
            return False

        if side == OrderType.BUY and not self.can_buy(price, qty):
            return False
        elif side == OrderType.SELL and not self.can_sell(price, qty):
            return False

        return True

    async def deliver_ok(self, order: Order):
        if order.side == OrderType.BUY:
            self.stats.buy_stats.delivered += 1
        else:
            self.stats.sell_stats.delivered += 1

        self.orders_in_last_second += 1
        await asyncio.sleep(
            sleep_seconds.wait_before_cancel
        )  # allow time for order to be filled

        self.open_orders.append(order)

        await self.cancel_open_orders()
        if order.side == OrderType.BUY:
            await asyncio.sleep(sleep_seconds.wait_after_deliver_buy)
        else:
            await asyncio.sleep(sleep_seconds.wait_after_deliver_sell)

    async def deliver_fail(self):
        self.stats.fail_counts.bad_response += 1

        # wait a bit, maybe gets better next time
        await asyncio.sleep(sleep_seconds.wait_after_failed_order)

    async def submit_ok(
        self,
        order_log: dict,
        side: OrderType,
        price: Decimal,
        qty: int,
    ):
        order_id = self.parse_order_id(order_log)
        if order_id:
            order = Order(
                order_id=order_id,
                side=side.value,
                price=price,
                qty=Decimal(qty),
                symbol=self.pair.symbol,
            )
            await self.deliver_ok(order)
        else:
            logger.info(f"{self.pair} {side} {qty} {price} : {order_log}")
            await self.deliver_fail()

    async def send_order(
        self,
        side: OrderType,
        price: Decimal,
        qty: int,
    ) -> Optional[OrderId]:
        try:
            if side == OrderType.BUY:
                lock = self.locks.buy
            else:
                lock = self.locks.sell

            if lock.locked():
                self.stats.fail_counts.self_lock += 1
                return None

            async with lock:
                if not self.can_order(side, price, qty):
                    return None

                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side, float(price), qty
                )
                if order_log:
                    await self.submit_ok(order_log, side, price, qty)
                else:
                    self.stats.fail_counts.parent += 1
            return None
        except Exception as e:
            msg = f"send_order: {e}: [{side, price, qty}], {traceback.format_exc()}"
            logger.info(msg)
            log_pub.publish_error(message=msg)
            return None

    @staticmethod
    def parse_order_id(order_log: dict) -> Optional[OrderId]:
        data = order_log.get("data", {})
        if data:
            return data.get("id")
        return None
