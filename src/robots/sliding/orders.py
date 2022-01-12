import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import simplejson as json  # type: ignore

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.environment import sleep_seconds
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
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    order_lock: asyncio.Lock = asyncio.Lock()
    open_orders: OpenOrders = OpenOrders()

    orders_delivered: OrdersDelivered = OrdersDelivered()
    prev_order_count: int = 0

    @asynccontextmanager
    async def timeout_lock(self, timeout=sleep_seconds.wait_between_orders_for_robots):
        async with self.order_lock:
            yield
            await asyncio.sleep(timeout)

    async def cancel_all_open_orders(self) -> None:
        try:
            if self.orders_delivered.total in (0, self.prev_order_count):
                return

            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if not res:
                return None
            
            
            (
                sell_ids,
                buy_ids,
            ) = self.exchange.parse_open_orders(res)

            if buy_ids:
                await self.exchange.cancel_multiple_orders(buy_ids)
            if sell_ids:
                await self.exchange.cancel_multiple_orders(sell_ids)

            self.prev_order_count = self.orders_delivered.total

        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:
        if self.order_lock.locked():
            return None

        async with self.timeout_lock():
            try:
                if side == OrderType.BUY and self.open_orders.buy:
                    await self.exchange.cancel_order(self.open_orders.buy.pop())

                if side == OrderType.SELL and self.open_orders.sell:
                    await self.exchange.cancel_order(self.open_orders.sell.pop())

                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side.value, float(price), float(qty)
                )
                if order_log:
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
                msg = f"send_order: {e}: [{side, price, self.config.base_step_qty}]"
                logger.info(msg)
                log_pub.publish_error(message=msg)
                return None

    @staticmethod
    def parse_order_id(order_log: dict):
        return order_log.get("data", {}).get("id")
