import asyncio
import copy
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import src.pubsub.pub as pub
from src.domain import OrderType
from src.exchanges.base import ExchangeAPIClientBase
from src.monitoring import logger
from src.periodic import SingleTaskContext
from src.robots.sliding.orders import OrderApi
from src.robots.watchers import BookPub, BalancePub
from src.stgs.sliding.config import SlidingWindowConfig


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class MarketWatcher:
    config: SlidingWindowConfig

    book_station: BookPub
    balance_station: BalancePub

    prices: MarketPrices = MarketPrices()

    start_balances_saved: bool = False
    fresh_price_task: SingleTaskContext = SingleTaskContext()

    def __post_init__(self):

        self.order_api = OrderApi(
            config=self.config,
            pair=self.config.create_pair(),
            exchange=self.book_station.api_client,
        )

        self.pair = self.config.create_pair()

        self.start_pair = self.config.create_pair()

    async def update_prices(self) -> None:
        async for book in self.book_station.stream:
            try:
                async with self.fresh_price_task.refresh_task(self.clear_prices):
                    self.prices.ask = self.book_station.api_client.get_best_ask(book)

                    self.prices.bid = self.book_station.api_client.get_best_bid(book)

                await asyncio.sleep(0)

            except Exception as e:
                msg = f"update_follower_prices: {e}"
                logger.error(msg)
                pub.publish_error(message=msg)

    async def clear_prices(self):
        await asyncio.sleep(self.config.sleep_seconds.clear_prices)
        self.prices = MarketPrices()

    async def update_balances(self) -> None:
        try:
            res: Optional[dict] = self.balance_station.balances
            if not res:
                return

            balances = self.book_station.api_client.parse_account_balance(
                res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
            )

            base_balances: dict = balances[self.pair.base.symbol]
            self.pair.base.free = Decimal(base_balances["free"])
            self.pair.base.locked = Decimal(base_balances["locked"])

            quote_balances: dict = balances[self.pair.quote.symbol]
            self.pair.quote.free = Decimal(quote_balances["free"])
            self.pair.quote.locked = Decimal(quote_balances["locked"])

            if not self.start_balances_saved:
                self.start_pair = copy.deepcopy(self.pair)
                self.start_balances_saved = True

        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            pub.publish_error(message=msg)
            raise e

    def can_buy(self, price) -> bool:
        return (
            bool(self.pair.quote.free)
            and self.pair.quote.free >= price * self.config.base_step_qty
        )

    async def long(self, price: Decimal) -> Optional[dict]:
        if not self.can_buy(price):
            return None

        order_log = await self.order_api.send_order(
            OrderType.BUY, price, self.config.base_step_qty
        )

        if order_log:
            # If we deliver order, we reflect it in balance until we read the current balance
            self.pair.base.free += self.config.base_step_qty
            return order_log

        return None

    async def short(self, price: Decimal) -> Optional[dict]:
        qty = self.config.base_step_qty

        if self.pair.base.free < qty:
            qty = self.pair.base.free * Decimal("0.98")

        order_log = await self.order_api.send_order(OrderType.SELL, price, qty)

        if order_log:
            # If we deliver order, we reflect it in balance until we read the current balance
            self.pair.base.free -= self.config.base_step_qty
            return order_log
        return None
