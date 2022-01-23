import asyncio
import collections
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.locks import Locks
from src.monitoring import logger
from src.stgs import LeaderFollowerConfig


@dataclass
class OrderStats:
    buy_delivered: int = 0
    sell_delivered: int = 0
    robot_locked: int = 0
    parent_locked: int = 0
    deliver_fail: int = 0
    cancelled: int = 0
    cancel_fail: int = 0
    refreshed: int = 0
    refresh_fail: int = 0
    read_locked: int = 0
    cant_buy: int = 0
    cant_sell: int = 0
    cant_buy_open_orders: int = 0
    cant_sell_open_orders: int = 0


@dataclass
class OpenOrders:
    buy: set = field(default_factory=set)
    sell: set = field(default_factory=set)


@dataclass
class OrderApi:
    config: LeaderFollowerConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    open_order_ids: collections.deque = field(default_factory=collections.deque)
    cancelled_order_ids: set = field(default_factory=set)
    open_order_qtys: dict = field(default_factory=dict)

    open_orders: OpenOrders = field(default_factory=OpenOrders)

    stats: OrderStats = field(default_factory=OrderStats)

    locks: Locks = field(default_factory=Locks)
    open_orders_fresh: bool = True

    def refresh_open_order_successful(self, orderlist: list) -> None:
        orders = {order.get("id"): order for order in orderlist}
        order_ids = list(orders.keys())

        for order_id in order_ids:
            if order_id not in self.cancelled_order_ids:
                self.open_order_ids.append(order_id)

        self.cancelled_order_ids = set()

        still_open = set(self.open_order_ids)

        self.open_order_qtys = {
            order_id: Decimal(orders.get(order_id, {}).get("leftAmount", 0))
            for order_id in self.open_order_qtys
            if order_id in still_open
        }
        self.open_orders.buy = set([o for o in self.open_orders.buy if o in still_open])
        self.open_orders.sell = set(
            [o for o in self.open_orders.sell if o in still_open]
        )
        self.open_orders_fresh = True
        self.stats.refreshed += 1

    async def refresh_open_orders(self) -> None:
        if self.open_orders_fresh:
            return None

        if self.locks.read.locked():
            self.stats.read_locked += 1
            return None

        async with self.locks.read:
            await self.wait_for_lock(self.exchange.locks.read)

            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if res:
                orders = self.exchange.get_sorted_order_list(res)
                self.refresh_open_order_successful(orders)
            else:
                self.stats.refresh_fail += 1

        await self.cancel_open_orders()

    def cancel_successful(self, order_id) -> None:
        self.cancelled_order_ids.add(order_id)
        self.stats.cancelled += 1
        if order_id in self.open_order_qtys:
            self.pair.base.free += self.open_order_qtys[order_id]
            del self.open_order_qtys[order_id]

        if order_id in self.open_orders.buy:
            self.open_orders.buy.remove(order_id)
        elif order_id in self.open_orders.sell:
            self.open_orders.sell.remove(order_id)

    def cancel_failed(self) -> None:
        # couldn't cancel but maybe filled
        self.open_orders_fresh = False
        self.stats.cancel_fail += 1

    async def wait_for_lock(self, lock):
        while lock.locked():
            await asyncio.sleep(0.05)

    async def cancel_order(self, order_id) -> None:
        await self.wait_for_lock(self.exchange.locks.cancel)

        ok = await self.exchange.cancel_order(order_id)

        if ok:
            self.cancel_successful(order_id)
        else:
            self.cancel_failed()

    async def cancel_open_orders(self) -> None:
        try:
            if not self.open_order_ids:
                return None

            if self.locks.cancel.locked():
                return None

            async with self.locks.cancel:
                while self.open_order_ids:
                    order_id = self.open_order_ids.popleft()
                    if order_id in self.cancelled_order_ids:
                        continue
                    await self.cancel_order(order_id)

                if self.open_orders_fresh:
                    self.cancelled_order_ids = set()

        except Exception as e:
            msg = f"cancel_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def order_delivered(self, order_id: OrderId, side: OrderType, qty: int):
        if side == OrderType.BUY:
            self.stats.buy_delivered += 1
            self.pair.base.free += qty
            self.open_order_qtys[order_id] = -1 * qty
            self.open_orders.buy.add(order_id)
        else:
            self.stats.sell_delivered += 1
            self.pair.base.free -= qty
            self.open_order_qtys[order_id] = qty
            self.open_orders.sell.add(order_id)

        await asyncio.sleep(0.09)  # allow time for order to be filled
        self.open_order_ids.append(order_id)
        await asyncio.sleep(0.1)

    def order_delivered_but_failed(self, order_log):
        self.stats.deliver_fail += 1

    def parent_locked(self):
        self.stats.parent_locked += 1

    def get_order_lock(self, side):
        return self.locks.buy if side == OrderType.BUY else self.locks.sell

    def can_sell(self, price, qty) -> bool:
        return self.pair.base.free >= qty and qty * price >= self.config.min_sell_qty

    def can_buy(self, price, qty) -> bool:
        return (
            bool(self.pair.quote.free)
            and self.pair.quote.free >= price * qty > self.config.min_buy_qty
        )

    async def send_order(
        self, side: OrderType, price: Decimal, qty: int
    ) -> Optional[OrderId]:
        try:

            order_lock = self.get_order_lock(side)
            if order_lock.locked():
                self.stats.robot_locked += 1
                return None

            if side == OrderType.BUY:
                if not self.can_buy(price, qty):
                    self.stats.cant_buy += 1
                    return None
                if self.open_orders.buy:
                    self.stats.cant_buy_open_orders += 1
                    return None
            elif side == OrderType.SELL:
                if not self.can_sell(price, qty):
                    self.stats.cant_sell += 1
                    return None
                if self.open_orders.sell:
                    self.stats.cant_sell_open_orders += 1
                    return None

            async with order_lock:
                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side, float(price), qty
                )
                if order_log:
                    order_id = self.parse_order_id(order_log)
                    if order_id:
                        await self.order_delivered(order_id, side, qty)
                    else:
                        self.order_delivered_but_failed(order_log)
                        logger.info(
                            f"{self.pair} {side} {int(qty)} {price} : {order_log}"
                        )
                        await asyncio.sleep(
                            0.1
                        )  # wait a bit, maybe gets better next time
                else:
                    self.parent_locked()
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
