import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import simplejson as json  # type: ignore

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.base import ExchangeBase
from blackops.robots.config import SlidingWindowConfig
from blackops.util.logger import logger


@dataclass
class OrderRobot:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: ExchangeBase

    long_in_progress: bool = False
    short_in_progress: bool = False

    open_sell_orders: list = field(default_factory=list)
    open_buy_orders: list = field(default_factory=list)

    buy_orders_delivered: int = 0
    sell_orders_delivered: int = 0

    def __post_init__(self):
        self.channel = self.config.sha

    async def watch_open_orders(self) -> None:
        try:
            open_orders: Optional[dict] = await self.exchange.get_open_orders(self.pair)
            if not open_orders:
                open_orders = {}

            (
                self.open_sell_orders,
                self.open_buy_orders,
            ) = self.exchange.parse_open_orders(open_orders)

        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)

    async def cancel_all_open_orders(self) -> bool:
        try:
            if self.open_sell_orders or self.open_buy_orders:
                await self.exchange.cancel_multiple_orders(
                    self.open_sell_orders + self.open_buy_orders
                )
            return True
        except Exception as e:
            msg = f"cancel_all_open_orders: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)
            return False

    def can_buy(self, best_seller: Decimal) -> bool:
        if best_seller and not self.long_in_progress:
            return True

        return False

    def can_sell(self, best_buyer: Decimal) -> bool:
        if best_buyer and self.config.base_step_qty and not self.short_in_progress:
            return True

        return False

    async def send_long_order(
        self, best_seller: Decimal, theo_buy: Decimal
    ) -> Optional[dict]:
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum
        if not self.can_buy(best_seller):
            return None

        price = float(best_seller)
        qty = float(self.config.base_step_qty)  #  we buy base

        try:
            self.long_in_progress = True
            order_log = await self.send_order("buy", price, qty)
            if order_log:
                order_log["theo"] = theo_buy
                self.buy_orders_delivered += 1
                return order_log
            return None

        except Exception as e:
            msg = f"long: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)
            return None
        finally:
            await asyncio.sleep(0.1)
            self.long_in_progress = False

    async def send_short_order(
        self, best_buyer: Decimal, theo_sell: Decimal
    ) -> Optional[dict]:
        if not self.can_sell(best_buyer):
            return None

        price = float(best_buyer)
        qty = float(self.config.base_step_qty)  # we sell base

        try:
            self.short_in_progress = True
            order_log = await self.send_order("sell", price, qty)
            if order_log:
                order_log["theo"] = theo_sell
                self.sell_orders_delivered += 1
                return order_log
            return None
        except Exception as e:
            msg = f"short: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)
            return None
        finally:
            await asyncio.sleep(0.1)
            self.short_in_progress = False

    async def send_order(self, side, price, qty) -> Optional[dict]:
        try:
            res: Optional[dict] = await self.exchange.submit_limit_order(
                self.pair, side, price, qty
            )
            ok = (
                res
                and isinstance(res, dict)
                and res.get("success", False)
                and res.get("data", None)
            )
            if not ok:
                msg = f"could not send order to {side} {qty} {self.pair.base.symbol} at {price}, response: {res}"
                logger.info(msg)
                return None

            return res

        except Exception as e:
            msg = f"send_order: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)
            return None
