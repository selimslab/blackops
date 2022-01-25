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


@dataclass
class DeliveredCounts:
    buy: int = 0
    sell: int = 0


@dataclass
class FailCounts:
    buy_check: int = 0
    sell_check: int = 0
    open: int = 0
    hit_order_limit = 0
    parent: int = 0
    bad_response: int = 0


@dataclass
class OrderStats:
    fail_counts: FailCounts = field(default_factory=FailCounts)

    delivered_counts: DeliveredCounts = field(default_factory=DeliveredCounts)
    cancelled: int = 0
    probably_filled: int = 0

    refreshed: int = 0
    refresh_fail: int = 0
    read_locked: int = 0


@dataclass
class Order:
    order_id: OrderId
    symbol: str
    side: OrderType
    price: Decimal
    qty: Decimal


@dataclass
class OrderApi:
    config: LeaderFollowerConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    open_orders: collections.deque = field(default_factory=collections.deque)
    cancelled_order_ids: set = field(default_factory=set)

    stats: OrderStats = field(default_factory=OrderStats)

    locks: Locks = field(default_factory=Locks)
    open_orders_fresh: bool = True

    orders_in_last_second: int = 0
    max_orders_per_second: int = 4

    last_buy_price: Optional[Decimal] = None
    last_sell_price: Optional[Decimal] = None

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
                    order: Order = self.open_orders.popleft()
                    if order.order_id in self.cancelled_order_ids:
                        continue
                    await self.cancel_order(order)

                if self.open_orders_fresh:
                    self.cancelled_order_ids = set()

        except Exception as e:
            msg = f"cancel_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def cancel_order(self, order: Order) -> None:
        await self.poll_for_lock(self.exchange.locks.cancel)

        ok = await self.exchange.cancel_order(order.order_id)

        if ok:
            self.cancel_successful(order)
        else:
            self.cancel_failed(order)

    def cancel_successful(self, order: Order) -> None:
        self.cancelled_order_ids.add(order.order_id)
        self.stats.cancelled += 1
        if order.side == OrderType.BUY:
            self.pair.base.free -= order.qty
        else:
            self.pair.base.free += order.qty

    def cancel_failed(self, order: Order) -> None:
        # couldn't cancel but maybe filled
        self.open_orders_fresh = False
        self.stats.probably_filled += 1
        if order.side == OrderType.BUY:
            self.last_buy_price = order.price
        else:
            self.last_sell_price = order.price

    async def poll_for_lock(self, lock):
        while lock.locked():
            await asyncio.sleep(sleep_seconds.poll_for_lock)

    async def refresh_open_orders(self) -> None:
        if self.open_orders_fresh:
            return None

        if self.locks.read.locked():
            self.stats.read_locked += 1
            return None

        async with self.locks.read:
            await self.poll_for_lock(self.exchange.locks.read)

            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if res:
                orderlist = self.exchange.get_sorted_order_list(res)
                self.refresh_open_order_successful(orderlist)
            else:
                self.stats.refresh_fail += 1

        await self.cancel_open_orders()

    def refresh_open_order_successful(self, orderlist: list) -> None:
        orders = [
            Order(
                order_id=order_dict.get("id"),
                price=Decimal(order_dict["price"]),
                qty=Decimal(order_dict.get("leftAmount", 0)),
                symbol=order_dict.get("pairSymbol"),
                side=OrderType(order_dict.get("type")),
            )
            for order_dict in orderlist
        ]

        for order in orders:
            if order.order_id not in self.cancelled_order_ids:
                self.open_orders.append(order)

        self.open_orders_fresh = True
        self.cancelled_order_ids = set()
        self.stats.refreshed += 1

    def can_sell(self, price, qty) -> bool:
        return self.pair.base.free >= qty and qty * price >= self.config.min_sell_qty

    def can_buy(self, price, qty) -> bool:
        return (
            bool(self.pair.quote.free)
            and self.pair.quote.free >= price * qty > self.config.min_buy_qty
        )

    def can_order(self, side: OrderType, price: Decimal, qty: int):

        if self.orders_in_last_second >= self.max_orders_per_second:
            self.stats.fail_counts.hit_order_limit += 1
            return None

        if self.open_orders:
            self.stats.fail_counts.open += 1
            return None

        if side == OrderType.BUY:
            if not self.can_buy(price, qty):
                self.stats.fail_counts.buy_check += 1
                return None
        elif side == OrderType.SELL:
            if not self.can_sell(price, qty):
                self.stats.fail_counts.sell_check += 1
                return None

    async def deliver_ok(self, order: Order):
        if order.side == OrderType.BUY:
            self.stats.delivered_counts.buy += 1
            self.pair.base.free += order.qty
        else:
            self.stats.delivered_counts.sell += 1
            self.pair.base.free -= order.qty

        self.orders_in_last_second += 1
        await asyncio.sleep(
            sleep_seconds.wait_before_cancel
        )  # allow time for order to be filled
        self.open_orders.append(order)
        await self.cancel_open_orders()

    async def deliver_fail(self):
        self.stats.fail_counts.bad_response += 1

        # wait a bit, maybe gets better next time
        await asyncio.sleep(sleep_seconds.wait_after_failed_order)

    async def send_order(
        self, side: OrderType, price: Decimal, qty: int
    ) -> Optional[OrderId]:
        try:
            if not self.can_order(side, price, qty):
                return None

            if self.locks.order.locked():
                return None

            async with self.locks.order:
                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side, float(price), qty
                )
                if order_log:
                    order_id = self.parse_order_id(order_log)
                    if order_id:
                        order = Order(
                            order_id=order_id,
                            side=side,
                            price=price,
                            qty=Decimal(qty),
                            symbol=self.pair.symbol,
                        )
                        await self.deliver_ok(order)
                    else:
                        # delivered but failed
                        logger.info(f"{self.pair} {side} {qty} {price} : {order_log}")
                        await self.deliver_fail()
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
