import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import simplejson as json  # type: ignore

import src.pubsub.pub as pub
from src.domain.asset import Asset, AssetPair
from src.exchanges.base import ExchangeAPIClientBase
from src.robots.config import SlidingWindowConfig
from src.monitoring import logger


@dataclass
class OrderRobot:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeAPIClientBase

    buy_lock: asyncio.Lock = asyncio.Lock()
    sell_lock: asyncio.Lock = asyncio.Lock()

    open_sell_orders: list = field(default_factory=list)
    open_buy_orders: list = field(default_factory=list)

    buy_orders_delivered: int = 0
    sell_orders_delivered: int = 0
    prev_order_count: int = 0

    @property
    def total_orders_delivered(self):
        return self.buy_orders_delivered + self.sell_orders_delivered

    def __post_init__(self):
        self.channel = self.config.sha

    async def cancel_all_open_orders(self) -> None:
        try:
            if self.total_orders_delivered in (0, self.prev_order_count):
                return

            open_orders: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if not open_orders:
                open_orders = {}

            (
                self.open_sell_orders,
                self.open_buy_orders,
            ) = self.exchange.parse_open_orders(open_orders)

            if self.open_sell_orders or self.open_buy_orders:
                await self.exchange.cancel_multiple_orders(
                    self.open_sell_orders + self.open_buy_orders
                )

            self.prev_order_count = self.total_orders_delivered

        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)

    def can_buy(self, best_seller: Decimal) -> bool:
        if best_seller and not self.buy_lock.locked():
            return True

        return False

    def can_sell(self, best_buyer: Decimal) -> bool:
        if best_buyer and self.config.base_step_qty and not self.sell_lock.locked():
            return True

        return False

    async def send_long_order(self, best_seller: Decimal) -> Optional[dict]:
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum
        if not self.can_buy(best_seller):
            return None

        price = float(best_seller)
        qty = float(self.config.base_step_qty)  #  we buy base

        with self.buy_lock:
            try:
                order_log = await self.submit_order("buy", price, qty)
                if not order_log:
                    return None

                order_id = self.parse_order_id(order_log)
                if order_id:
                    self.buy_orders_delivered += 1
                    return order_log
                return None
            except Exception as e:
                logger.info(f"send_long_order: {e}")
                return None

    async def send_short_order(self, best_buyer: Decimal, qty: float) -> Optional[dict]:
        if not self.can_sell(best_buyer):
            return None

        price = float(best_buyer)

        with self.sell_lock:
            try:
                order_log = await self.submit_order("sell", price, qty)
                if not order_log:
                    return None
                order_id = self.parse_order_id(order_log)
                if order_id:
                    self.sell_orders_delivered += 1
                    return order_log
                return None
            except Exception as e:
                logger.info(f"send_short_order: {e}")
                return None

    @staticmethod
    def parse_order_id(order_log: dict):
        data = order_log.get("data", {})
        order_id = data.get("id")
        return order_id

    async def submit_order(self, side, price, qty) -> Optional[dict]:
        try:
            res: Optional[dict] = await self.exchange.submit_limit_order(
                self.pair, side, price, qty
            )
            ok = (
                bool(res)
                and isinstance(res, dict)
                and res.get("success", False)
                and res.get("data", None)
            )
            if not ok:
                msg = f"could not send order to {side} {qty} {self.pair.base.symbol} at {price}, response: {res}"
                logger.info(msg)
                return None

            if res:
                return res

            return None
        except Exception as e:
            msg = f"send_order: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)
            return None
