import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import simplejson as json  # type: ignore

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.stgs.sliding.config import SlidingWindowConfig


@dataclass
class OpenOrders:
    buy: list = field(default_factory=list)
    sell: list = field(default_factory=list)


@dataclass
class OrdersDelivered:
    buy: int = 0
    sell: int = 0

    @property
    def total(self):
        return self.buy + self.sell


@dataclass
class OrderLocks:
    buy: asyncio.Lock = asyncio.Lock()
    sell: asyncio.Lock = asyncio.Lock()


@dataclass
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    order_locks: OrderLocks = OrderLocks()
    open_orders: OpenOrders = OpenOrders()

    orders_delivered: OrdersDelivered = OrdersDelivered()
    prev_order_count: int = 0

    @asynccontextmanager
    async def timeout_lock(self, lock, timeout=0.1):
        async with lock:
            yield
            await asyncio.sleep(timeout)

    async def cancel_all_open_orders(self) -> None:
        try:
            if self.orders_delivered.total in (0, self.prev_order_count):
                return

            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if not res:
                res = {}

            (
                self.open_orders.sell,
                self.open_orders.buy,
            ) = self.exchange.parse_open_orders(res)

            if self.open_orders.buy:
                await self.exchange.cancel_multiple_orders(self.open_orders.buy)
            if self.open_orders.sell:
                await self.exchange.cancel_multiple_orders(self.open_orders.sell)

            self.prev_order_count = self.orders_delivered.total

        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:
        if side == OrderType.BUY:
            lock = self.order_locks.buy
        else:
            lock = self.order_locks.sell

        if lock.locked():
            return None

        async with self.timeout_lock(lock):
            try:
                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side.value, float(price), float(qty)
                )
                if not order_log:
                    return None
                order_id = self.parse_order_id(order_log)
                if order_id:
                    if side == OrderType.BUY:
                        self.orders_delivered.buy += 1
                    else:
                        self.orders_delivered.sell += 1
                    return order_log
                return None
            except Exception as e:
                msg = f"send_order: {e}: [{side, price, self.config.base_step_qty}]"
                logger.info(msg)
                log_pub.publish_error(message=msg)
                return None

    @staticmethod
    def parse_order_id(order_log: dict):
        return order_log.get("data", {}).get("id")
