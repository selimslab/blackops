import asyncio
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
from src.numberops.main import get_precision, round_decimal_half_down  # type: ignore
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
class OrdersTried:
    buy: int = 0
    sell: int = 0
    buy_locked: int = 0
    sell_locked: int = 0


@dataclass
class OrderApi:
    config: SlidingWindowConfig
    pair: AssetPair
    exchange: BtcturkBase

    open_orders: OpenOrders = field(default_factory=OpenOrders)

    orders_delivered: OrdersDelivered = field(default_factory=OrdersDelivered)

    orders_tried: OrdersTried = field(default_factory=OrdersTried)

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

    # async def cancel_previous_order(self, side: OrderType) -> None:
    #     try:
    #         if side == OrderType.BUY and self.open_orders.buy:
    #             await self.exchange.cancel_order(self.open_orders.buy.pop())

    #         if side == OrderType.SELL and self.open_orders.sell:
    #             await self.exchange.cancel_order(self.open_orders.sell.pop())
    #     except Exception as e:
    #         pass

    async def send_order(
        self, side: OrderType, price: Decimal, qty: Decimal
    ) -> Optional[dict]:

        try:

            if side == OrderType.BUY and self.exchange.locks.buy.locked():
                self.orders_tried.buy_locked += 1
                return None
            elif side == OrderType.SELL and self.exchange.locks.sell.locked():
                self.orders_tried.sell_locked += 1
                return None

            float_qty = round(float(qty), get_precision(qty))

            order_log: Optional[dict] = await self.exchange.submit_limit_order(
                self.pair, side, float(price), float_qty
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
                if side == OrderType.BUY:
                    self.orders_tried.buy += 1
                else:
                    self.orders_tried.sell += 1

                logger.info(
                    f"cannot {side.value} {float_qty} ({qty}) {self.pair.symbol}  @ {price} "
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
