import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, List, Optional

import simplejson as json

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.environment import debug
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.btcturk.base import BtcturkBase
from blackops.robots.base import RobotBase
from blackops.robots.config import SlidingWindowConfig, StrategyType
from blackops.robots.stats import RobotStats
from blackops.util.logger import logger

getcontext().prec = 6


@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig
    pair: AssetPair

    # Exchanges
    leader_exchange: ExchangeBase
    follower_exchange: ExchangeBase

    # Streams
    leader_book_ticker_stream: AsyncGenerator
    follower_book_stream: AsyncGenerator
    leader_bridge_quote_stream: Optional[AsyncGenerator] = None

    # Realtime
    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell
    bridge_quote: Decimal = Decimal("1")

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None

    current_step: Decimal = Decimal("0")

    # orders
    longs: list = field(
        default_factory=list
    )  # track your orders and figure out balance
    shorts: list = field(
        default_factory=list
    )  # track your orders and figure out balance

    long_in_progress: bool = False
    short_in_progress: bool = False

    open_asks: Decimal = Decimal("0")
    open_bids: Decimal = Decimal("0")

    async def run(self):
        self.channnel = self.config.sha

        self.stats = SlidingWindowStats(robot=self, task_start_time=datetime.now())

        # this first call to read balances must be succesful or we exit
        await self.update_balances()
        self.start_base_balance = self.pair.base.balance
        self.start_quote_balance = self.pair.quote.balance

        self.current_step = self.pair.base.balance / self.config.base_step_qty

        await self.run_streams()

    async def stop(self):
        raise asyncio.CancelledError(f"{self.config.type.name} stopped")

    def get_orders(self):
        return self.longs + self.shorts

    async def run_streams(self):
        logger.info(f"Start streams for {self.config.type.name}")

        consumers: Any = [
            self.watch_leader(),
            self.watch_follower(),
            self.stats.broadcast_stats_periodical(),
            self.update_balances_periodically(),
            self.update_open_order_balance(),
        ]  # is this ordering important ?
        if self.config.bridge:
            consumers.append(self.watch_bridge())

        await asyncio.gather(*consumers)

    async def watch_leader(self):
        async for book in self.leader_book_ticker_stream:
            if book:
                self.stats.binance_book_ticker_stream_seen += 1
                self.calculate_window(book)
                await self.should_transact()
            await asyncio.sleep(0)

    async def watch_follower(self):
        async for book in self.follower_book_stream:
            if book:
                parsed_book = self.follower_exchange.parse_book(book)
                self.update_follower_prices(parsed_book)
                self.stats.btc_books_seen += 1

            await asyncio.sleep(0)

    async def watch_bridge(self):
        if not self.leader_bridge_quote_stream:
            raise ValueError("No bridge quote stream")

        async for book in self.leader_bridge_quote_stream:
            new_quote = self.leader_exchange.get_mid(book)
            if new_quote:
                self.bridge_quote = new_quote
                self.stats.bridge_last_updated = datetime.now().time()
            await asyncio.sleep(0)

    async def update_open_order_balance(self):
        prev_order_count = -1
        while True:
            await asyncio.sleep(0.2)
            order_count = len(self.longs) + len(self.shorts)
            if order_count == prev_order_count:
                continue
            (
                self.open_asks,
                self.open_bids,
            ) = await self.follower_exchange.get_open_asks_and_bids(self.pair)
            prev_order_count = order_count

    async def update_balances(self):
        try:
            balances: dict = await self.follower_exchange.get_account_balance(
                symbols=[self.pair.base.symbol, self.pair.quote.symbol]
            )

            base_balances: dict = balances[self.pair.base.symbol]
            self.pair.base.balance = Decimal(base_balances["free"]) + Decimal(
                base_balances["locked"]
            )

            quote_balances: dict = balances[self.pair.quote.symbol]
            self.pair.quote.balance = Decimal(quote_balances["free"]) + Decimal(
                quote_balances["locked"]
            )

        except Exception as e:
            msg = f"could not read balances: {e}"
            pub.publish_error(self.channnel, msg)
            raise Exception(msg)

    async def update_balances_periodically(self):
        # raises Exception if cant't read balance
        while True:
            try:
                await self.update_balances()
                self.current_step = self.pair.base.balance / self.config.base_step_qty
            except Exception as e:
                logger.info(e)
                # continue trying to read balances

            await asyncio.sleep(0.7)  # 90 rate limit

    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""

        if not book:
            return

        mid = self.leader_exchange.get_mid(book)

        if not mid:
            return

        mid = mid * self.bridge_quote

        step_size = self.config.step_constant_k * self.current_step

        mid -= step_size  # go down as you buy, we wish to buy lower as we buy

        self.theo_buy = mid - self.config.credit
        self.theo_sell = mid + self.config.credit

        self.stats.theo_last_updated = datetime.now()

    def update_follower_prices(self, book: dict):
        if not book:
            return
        try:
            best_ask = self.follower_exchange.get_best_ask(book)
            if best_ask:
                self.best_seller = best_ask

            best_bid = self.follower_exchange.get_best_bid(book)
            if best_bid:
                self.best_buyer = best_bid

            self.stats.bid_ask_last_updated = datetime.now()

        except Exception as e:
            logger.info(e)

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def have_usable_balance(self) -> bool:
        """Its still an approximation, but it's better than nothing"""
        total_used = Decimal("0")
        used_quote = self.start_quote_balance - self.pair.quote.balance
        total_used += used_quote
        # we may not be able to buy from the best seller
        safety_margin = Decimal("1.01")
        if self.best_seller:
            open_bid_cost = (
                self.open_bids
                * self.best_seller
                * self.follower_exchange.buy_with_fee  # type: ignore
                * safety_margin
            )
            total_used += open_bid_cost
        return total_used < self.config.max_usable_quote_amount_y

    def should_long(self):
        # we don't enforce max_usable_quote_amount_y too strict
        # we assume no deposits to quote during the task run
        return (
            self.best_seller
            and self.theo_buy
            and self.best_seller <= self.theo_buy
            and self.pair.quote.balance > self.best_seller * self.config.base_step_qty
            and self.have_usable_balance()
        )

    def should_short(self):
        #  act only when you are ahead
        # TODO we can check if we have enough base balance to short
        return (
            self.best_buyer
            and self.theo_sell
            and self.best_buyer >= self.theo_sell
            and self.pair.base.balance
        )

    async def long(self):
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum

        if not self.best_seller:
            return

        if self.long_in_progress:
            return

        price = float(self.best_seller)
        qty = float(self.config.base_step_qty)  #  we buy base

        try:
            self.long_in_progress = True
            order_log = await self.send_order("buy", price, qty, self.theo_buy)
            if order_log:
                self.longs.append(order_log)
                await self.stats.update_pnl()
        except Exception as e:
            logger.info(e)
        finally:
            self.long_in_progress = False

    async def short(self):
        if not self.best_buyer or not self.config.base_step_qty:
            return

        if self.short_in_progress:
            return

        price = float(self.best_buyer)
        qty = float(self.config.base_step_qty)  # we sell base

        try:
            self.short_in_progress = True
            order_log = await self.send_order("sell", price, qty, self.theo_sell)
            if order_log:
                self.shorts.append(order_log)
                await self.stats.update_pnl()
        except Exception as e:
            logger.info(e)
        finally:
            self.short_in_progress = False

    async def send_order(self, side, price, qty, theo):
        try:
            res = await self.follower_exchange.submit_limit_order(
                self.pair, side, price, qty
            )
            if not res:
                msg = f"no response for order request {side} {price} {qty}"
                raise Exception(msg)

            is_ok = res and res.get("success") and res.get("data")
            if not is_ok:
                msg = f"could not {side} {qty} {self.pair.base.symbol} for {price}, reason: {res}"
                raise Exception(msg)

            if res and res.get("data"):

                data = res.get("data", {})

                ts = data.get("datetime")
                order_time = datetime.fromtimestamp(ts / 1000.0)

                order_log = {
                    "time": str(order_time),
                    "type": side,
                    "price": str(price),
                    "qty": str(qty),
                    "theo": str(theo),
                }

                return order_log

        except Exception as e:
            logger.info(e)
            pub.publish_message(self.channnel, f"send_order: {str(e)}")


@dataclass
class SlidingWindowStats(RobotStats):
    robot: SlidingWindowTrader

    theo_last_updated: datetime = datetime.now()
    bid_ask_last_updated: datetime = datetime.now()
    bridge_last_updated: Optional[Any] = None

    binance_book_ticker_stream_seen: int = 0
    btc_books_seen: int = 0

    def __post_init__(self):
        self.config_dict = self.robot.config.dict()

    def broadcast_stats(self):
        message = self.create_stats_message()

        # if debug:
        #     logger.info(message)

        message = json.dumps(message, default=str)

        pub.publish_stats(self.robot.channnel, message)

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            if self.robot.pair.base.balance is None or self.robot.best_buyer is None:
                return None

            # await self.update_balances()

            approximate_sales_gain: Decimal = (
                self.robot.pair.base.balance
                * self.robot.best_buyer
                * self.robot.follower_exchange.sell_with_fee  # type: ignore
            )

            return (
                self.robot.pair.quote.balance
                + approximate_sales_gain
                - self.robot.start_quote_balance
            )
        except Exception as e:
            logger.info(e)
            return None

    async def update_pnl(self):
        pnl = await self.calculate_pnl()
        if pnl:
            self.pnl = pnl
            self.max_pnl = max(self.max_pnl, pnl)

    def create_stats_message(self):
        stats = {
            "current time": datetime.now().time(),
            "running seconds": self.runtime_seconds(),
            "balances": {
                "start": {
                    "base": self.robot.start_base_balance,
                    "quote": self.robot.start_quote_balance,
                },
                "current": {
                    "base": self.robot.pair.base.balance,
                    "quote": self.robot.pair.quote.balance,
                    "step": self.robot.current_step,
                },
                "pnl": self.pnl,
                "max pnl ever seen": self.max_pnl,
            },
            "binance": {
                "theo": {
                    "buy": self.robot.theo_buy,
                    "sell": self.robot.theo_sell,
                    "last_updated": self.theo_last_updated.time(),
                },
                "bridge": {
                    "bridge_quote": self.robot.bridge_quote,
                    "bridge_last_updated": self.bridge_last_updated,
                },
                "books seen": self.binance_book_ticker_stream_seen,
            },
            "btcturk": {
                "bid": self.robot.best_buyer,
                "ask": self.robot.best_seller,
                "last_updated": self.bid_ask_last_updated.time(),
                "books seen": self.btc_books_seen,
            },
            "orders": {
                "longs": self.robot.longs,
                "shorts": self.robot.shorts,
                "open": {
                    "buy": self.robot.open_bids,
                    "sell": self.robot.open_asks,
                },
            },
            "config": self.config_dict,
        }

        return stats
