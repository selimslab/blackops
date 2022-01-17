import asyncio
import queue
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import async_timeout

import src.pubsub.log_pub as log_pub
from src.domain import Asset, AssetPair, OrderId, OrderType
from src.environment import sleep_seconds
from src.exchanges.base import ExchangeAPIClientBase
from src.exchanges.btcturk.base import BtcturkBase
from src.monitoring import logger
from src.numberops.main import get_precision, round_decimal_floor  # type: ignore
from src.periodic import StopwatchContext, lock_with_timeout
from src.stgs.sliding.config import SlidingWindowConfig


@dataclass
class OrderStats:
    tried: int = 0
    delivered: int = 0


@dataclass
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: BtcturkBase

    open_order_ids: queue.Queue = field(default_factory=queue.Queue)

    stopwatch_api: StopwatchContext = field(default_factory=StopwatchContext)

    read_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    order_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    cancelled: set = field(default_factory=set)

    stats: OrderStats = field(default_factory=OrderStats)

    async def refresh_open_orders(self) -> None:

        if self.read_lock.locked():
            return None

        async with self.read_lock:
            while self.exchange.locks.read.locked():
                await asyncio.sleep(0.02)
            res: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if res:
                orders = self.exchange.get_sorted_order_list(res)
                order_ids = [order.get("id") for order in orders]

                # clear queue
                while self.open_order_ids:
                    self.open_order_ids.get_nowait()

                for order_id in order_ids:
                    if order_id and order_id not in self.cancelled:
                        self.open_order_ids.put_nowait(order_id)

                self.cancelled = set()

    async def cancel_open_orders(self) -> None:
        try:
            if self.cancel_lock.locked():
                return None

            if self.open_order_ids.empty():
                return None

            async with self.cancel_lock:
                while self.open_order_ids:
                    order_id = self.open_order_ids.get_nowait()
                    while self.exchange.locks.cancel.locked():
                        await asyncio.sleep(0.02)
                    ok = await self.exchange.cancel_order(order_id)
                    if ok:
                        self.cancelled.add(order_id)
        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:

        try:
            if self.order_lock.locked():
                return None

            float_qty = round(float(qty))

            async with self.order_lock:
                order_log: Optional[dict] = await self.exchange.submit_limit_order(
                    self.pair, side, float(price), float_qty
                )
            if order_log:
                # only send result if order delivered
                order_id = self.parse_order_id(order_log)
                if order_id:
                    logger.info(order_log)
                    self.stats.delivered += 1
                    await asyncio.sleep(0.07)  # allow 70 ms for order to be filled
                    self.open_order_ids.put_nowait(order_id)
                    return order_log

            self.stats.tried += 1
            logger.info(
                f"cannot {side.value} {float_qty} ({qty}) {self.pair.symbol}  @ {price}, {order_log}"
            )
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
