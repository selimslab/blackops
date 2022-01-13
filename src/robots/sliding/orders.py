import asyncio
import itertools
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

import async_timeout
import simplejson as json  # type: ignore

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import StopwatchContext, timer_lock
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
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    order_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    open_orders: OpenOrders = field(default_factory=OpenOrders)

    orders_delivered: OrdersDelivered = field(default_factory=OrdersDelivered)

    stopwatch_api: StopwatchContext = field(default_factory=StopwatchContext)

    @asynccontextmanager
    async def timeout_lock(self, timeout=sleep_seconds.wait_between_orders_for_robots):
        async with self.order_lock:
            yield
            await asyncio.sleep(timeout)

    async def cancel_all_open_orders(self) -> None:
        try:
            async with async_timeout.timeout(sleep_seconds.cancel_all_open_orders):
                await self.exchange.cancel_all_open_orders(self.pair)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:
        if self.order_lock.locked():
            return None

        async with timer_lock(
            lock=self.order_lock, sleep=sleep_seconds.wait_between_orders_for_robots
        ):
            try:
                if side == OrderType.BUY and self.open_orders.buy:
                    await self.exchange.cancel_order(self.open_orders.buy.pop())

                if side == OrderType.SELL and self.open_orders.sell:
                    await self.exchange.cancel_order(self.open_orders.sell.pop())

                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side.value, float(price), float(qty)
                )
                if order_log:
                    # only send result if order delivered
                    order_id = self.parse_order_id(order_log)
                    if order_id:
                        if side == OrderType.BUY:
                            self.orders_delivered.buy += 1
                            self.open_orders.buy.append(order_id)
                        else:
                            self.orders_delivered.sell += 1
                            self.open_orders.sell.append(order_id)
                        return order_log
                return None
            except Exception as e:
                msg = f"send_order: {e}: [{side, price, self.config.base_step_qty}], {traceback.format_exc()}"
                logger.info(msg)
                log_pub.publish_error(message=msg)
                return None

    @staticmethod
    def parse_order_id(order_log: dict) -> Optional[OrderId]:
        data = order_log.get("data", {})
        if data:
            return data.get("id")
        return None
