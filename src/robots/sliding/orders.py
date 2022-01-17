import asyncio
import itertools
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import async_timeout
import simplejson as json  # type: ignore

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import StopwatchContext, lock_with_timeout
from src.stgs.sliding.config import SlidingWindowConfig


@dataclass
class OpenOrders:
    buy: list = field(default_factory=list)
    sell: list = field(default_factory=list)


@dataclass
class OrdersDelivered:
    buy: int = 0
    sell: int = 0
    prev_total: int = 0

    @property
    def total(self):
        return self.buy + self.sell


@dataclass
class OrderLocks:
    buy: asyncio.Lock = field(default_factory=asyncio.Lock)
    sell: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    locks: OrderLocks = field(default_factory=OrderLocks)

    open_orders: OpenOrders = field(default_factory=OpenOrders)

    orders_delivered: OrdersDelivered = field(default_factory=OrdersDelivered)

    stopwatch_api: StopwatchContext = field(default_factory=StopwatchContext)

    async def cancel_all_open_orders(self) -> None:
        if self.orders_delivered.total in (0, self.orders_delivered.prev_total):
            return None
        try:
            async with async_timeout.timeout(sleep_seconds.cancel_all_open_orders):
                await self.exchange.cancel_all_open_orders(self.pair)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
        finally:
            self.orders_delivered.prev_total = self.orders_delivered.total

    async def cancel_previous_order(self, side: OrderType) -> None:
        try:
            async with lock_with_timeout(
                lock=self.locks.cancel, sleep=sleep_seconds.robot_cancel
            ):
                if side == OrderType.BUY and self.open_orders.buy:
                    await self.exchange.cancel_order(self.open_orders.buy.pop())

                if side == OrderType.SELL and self.open_orders.sell:
                    await self.exchange.cancel_order(self.open_orders.sell.pop())

        except Exception as e:
            pass

    async def _send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:

        try:
            order_log: Optional[dict] = await self.exchange.submit_limit_order(
                self.pair, side, float(price), float(qty)
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

                    logger.info(order_log)
                    return order_log
            else:
                logger.info(
                    f"couldn't send order: {self.pair.symbol, side, price, qty}"
                )
            return None
        except Exception as e:
            msg = f"send_order: {e}: [{side, price, self.config.base_step_qty}], {traceback.format_exc()}"
            logger.info(msg)
            log_pub.publish_error(message=msg)
            return None

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:

        # await self.cancel_previous_order(side)

        if side == OrderType.BUY:
            lock = self.locks.buy
            wait = sleep_seconds.robot_buy
        else:
            lock = self.locks.sell
            wait = sleep_seconds.robot_sell

        async with lock_with_timeout(lock, wait) as ok:
            if ok:
                return await self._send_order(side, price, qty)
        return None

    @staticmethod
    def parse_order_id(order_log: dict) -> Optional[OrderId]:
        data = order_log.get("data", {})
        if data:
            return data.get("id")
        return None
