import asyncio
import copy
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import src.pubsub.log_pub as log_pub
from src.domain import OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.periodic import StopwatchContext, periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.sliding.orders import OrderApi
from src.stgs.sliding.config import SlidingWindowConfig


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class MarketWatcher:
    config: SlidingWindowConfig

    book_pub: BookPub
    balance_pub: BalancePub

    prices: MarketPrices = field(default_factory=MarketPrices)

    start_balances_saved: bool = False
    fresh_price_task: StopwatchContext = field(default_factory=StopwatchContext)

    def __post_init__(self):

        self.order_api = OrderApi(
            config=self.config,
            pair=create_asset_pair(self.config.input.base, self.config.input.quote),
            exchange=self.book_pub.api_client,
        )

        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

        self.start_pair = create_asset_pair(
            self.config.input.base, self.config.input.quote
        )

    async def consume_pub(self) -> None:
        gen = create_book_consumer_generator(self.book_pub)
        async for book in gen:
            await self.update_prices(book)

    async def update_prices(self, book) -> None:
        try:
            ask = self.book_pub.api_client.get_best_ask(book)
            bid = self.book_pub.api_client.get_best_bid(book)
            if ask and bid:
                async with self.fresh_price_task.stopwatch(
                    self.clear_prices, sleep_seconds.clear_prices
                ):
                    self.prices.ask = ask
                    self.prices.bid = bid

            await asyncio.sleep(0)

        except Exception as e:
            msg = f"update_follower_prices: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    def clear_prices(self):
        self.prices = MarketPrices()

    async def update_balances(self) -> None:
        try:
            res: Optional[dict] = self.balance_pub.balances
            if not res:
                return

            balances = self.book_pub.api_client.parse_account_balance(
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
            log_pub.publish_error(message=msg)
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
            self.pair.base.free -= qty
            return order_log
        return None
