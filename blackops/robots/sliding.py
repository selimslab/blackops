import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, List, Optional

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.environment import debug
from blackops.exchanges.base import ExchangeBase
from blackops.robots.base import RobotBase
from blackops.robots.config import StrategyType
from blackops.taskq.redis import async_redis_client
from blackops.util.logger import logger

getcontext().prec = 6


@dataclass
class SlidingWindowTrader(RobotBase):
    """
    Move down the window as you buy,

    it means
    buy lower as you buy,
    go higher as you sell

    """

    #  Params

    sha: str

    pair: AssetPair

    max_usable_quote_amount_y: Decimal

    base_step_qty: Decimal  # buy 200 base per step

    credit: Decimal

    step_constant_k: Decimal

    # Exchanges
    leader_exchange: ExchangeBase
    follower_exchange: ExchangeBase

    leader_book_ticker_stream: AsyncGenerator
    follower_book_stream: AsyncGenerator
    binance_book_ticker_stream_seen: int = 0
    btc_books_seen: int = 0

    # Internals

    bridge_symbol: Optional[str] = None
    leader_bridge_quote_stream: Optional[AsyncGenerator] = None
    bridge_quote: Decimal = Decimal("1")
    bridge_last_updated: Optional[Any] = None

    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell
    theo_last_updated: datetime = datetime.now()

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None
    bid_ask_last_updated: datetime = datetime.now()

    orders: dict = field(
        default_factory=dict
    )  # track your orders and figure out balance

    orders_in_progress_balance: Decimal = Decimal("0")

    pnl: Decimal = Decimal("0")
    max_pnl: Decimal = Decimal("0")

    current_step: Decimal = Decimal("0")
    type: StrategyType = StrategyType.SLIDING_WINDOW

    # remaining_usable_quote_balance: Decimal = Decimal("0")

    #  NOTES

    # if we don't have a manual step_size_constant, step_size_constant = mid *

    # if we don't have a manual credit, credit could be fee_percent *
    # Decimal(1.5)

    # fee_percent * Decimal(1.5)
    # Decimal(0.001)

    debug_keys: tuple = (
        "runtime",
        "base_balance",
        "quote_balance",
        "orders",
        "pnl",
        "max_pnl",
        "binance_seen",
        "btc_seen",
    )

    long_in_progress: bool = False
    short_in_progress: bool = False

    open_order_balance: Decimal = Decimal("0")

    async def run(self):
        self.channnel = self.sha

        self.task_start_time: datetime = datetime.now()

        # this first call to read balances must be succesful or we exit
        await self.update_balances()
        self.current_step = self.pair.base.balance / self.base_step_qty

        self.start_base_balance = self.pair.base.balance
        self.start_quote_balance = self.pair.quote.balance

        self.params_message = self.create_params_message()

        await self.run_streams()

    async def stop(self):
        raise asyncio.CancelledError(f"{self.type.name} stopped")

    def get_orders(self):
        return self.orders

    async def run_streams(self):
        logger.info(f"Start streams for {self.type.name}")

        consumers: Any = [
            self.watch_leader(),
            self.watch_follower(),
            self.broadcast_stats_periodical(),
            self.update_balances_periodically(),
            self.update_open_order_balance(),
        ]  # is this ordering important ?
        if self.bridge_symbol:
            consumers.append(self.watch_bridge())

        await asyncio.gather(*consumers)

    async def watch_leader(self):
        async for book in self.leader_book_ticker_stream:
            if book:
                self.binance_book_ticker_stream_seen += 1
                self.calculate_window(book)
                await self.should_transact()
            await asyncio.sleep(0)

    async def watch_follower(self):
        async for book in self.follower_book_stream:
            if book:
                parsed_book = self.follower_exchange.parse_book(book)
                self.update_follower_prices(parsed_book)
                self.btc_books_seen += 1

            await asyncio.sleep(0)

    async def watch_bridge(self):
        if not self.leader_bridge_quote_stream:
            raise ValueError("No bridge quote stream")

        async for book in self.leader_bridge_quote_stream:
            new_quote = self.leader_exchange.get_mid(book)
            if new_quote:
                self.bridge_quote = new_quote
                self.bridge_last_updated = datetime.now().time()
            await asyncio.sleep(0)

    async def update_open_order_balance(self):
        prev_order_count = -1
        while True:
            await asyncio.sleep(0.2)
            order_count = len(self.orders)
            if order_count == prev_order_count:
                continue
            self.open_order_balance = (
                await self.follower_exchange.get_open_order_balance(self.pair.symbol)
            )
            prev_order_count = order_count

    async def update_balances(self):
        try:
            balances: dict = await self.follower_exchange.get_account_balance(
                assets=[self.pair.base.symbol, self.pair.quote.symbol]
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
                self.current_step = self.pair.base.balance / self.base_step_qty
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

        step_size = self.step_constant_k * self.current_step

        mid -= step_size  # go down as you buy, we wish to buy lower as we buy

        self.theo_buy = mid - self.credit
        self.theo_sell = mid + self.credit

        self.theo_last_updated = datetime.now()

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

            self.bid_ask_last_updated = datetime.now()

        except Exception as e:
            logger.info(e)

    async def should_transact(self):
        if self.should_long():
            await self.long()

        if self.should_short():
            await self.short()

    def have_usable_balance(self) -> bool:
        total_used = Decimal("0")
        used_quote = self.start_quote_balance - self.pair.quote.balance
        total_used += used_quote
        if self.best_buyer and self.open_order_balance:
            open_base_cost = self.open_order_balance * self.best_buyer
            total_used += open_base_cost
        return total_used < self.max_usable_quote_amount_y

    def should_long(self):
        # we don't enforce max_usable_quote_amount_y too strict
        # we assume no deposits to quote during the task run
        return (
            self.best_seller
            and self.theo_buy
            and self.best_seller <= self.theo_buy
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
        qty = float(self.base_step_qty)  #  we buy base

        await self.send_order("buy", price, qty)

    async def short(self):
        if not self.best_buyer or not self.base_step_qty:
            return

        if self.short_in_progress:
            return

        price = float(self.best_buyer)
        qty = float(self.base_step_qty)  # we sell base

        await self.send_order("sell", price, qty)

    async def send_order(self, side, price, qty):

        if side == "buy":
            theo = self.theo_buy
            self.long_in_progress = True
        elif side == "sell":
            theo = self.theo_sell
            self.short_in_progress = True
        else:
            raise Exception("invalid side")

        try:

            res = await self.follower_exchange.submit_limit_order(
                self.pair, side, price, qty
            )

            is_ok = res and res.get("success") and res.get("data")
            if not is_ok:
                msg = f"could not {side} {qty} {self.pair.base.symbol} for {price}, reason: {res}"
                raise Exception(msg)

            if res and res.get("data"):

                data = res.get("data", {})

                ts = data.get("datetime")
                order_time = datetime.fromtimestamp(ts / 1000.0)

                order_id = data.get("id")
                self.orders[order_id] = data

                # to enforce max amount we need to know about open orders
                if side == "buy":
                    self.orders_in_progress_balance += qty
                elif side == "sell":
                    self.orders_in_progress_balance -= qty

                self.log_order(side, order_time, price, qty, theo)

                await self.update_pnl()

        except Exception as e:
            logger.info(e)
            pub.publish_message(self.channnel, f"send_order: {str(e)}")
        finally:
            if side == "buy":
                self.long_in_progress = False
            elif side == "sell":
                self.short_in_progress = False

    # MONITORING

    def log_order(self, side, order_time, price, qty, theo):
        order_log = {
            "type": side,
            "time": str(order_time),
            "price": str(price),
            "qty": str(qty),
            "theo": str(theo),
        }

        pub.publish_order(self.channnel, order_log)

        logger.info(order_log)

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            if not self.start_quote_balance:
                return None

            # await self.update_balances()

            approximate_sales_gain: Decimal = (
                self.pair.base.balance * self.best_buyer * self.follower_exchange.sell_with_fee  # type: ignore
            )

            return (
                self.pair.quote.balance
                + approximate_sales_gain
                - self.start_quote_balance
            )
        except Exception as e:
            logger.info(e)
            return None

    async def update_pnl(self):
        pnl = await self.calculate_pnl()
        if pnl:
            self.pnl = pnl
            self.max_pnl = max(self.max_pnl, pnl)

    def create_params_message(self):
        return {
            "name": self.type.name,
            "pair": self.pair.symbol,
            "max_usable_quote_amount_y": str(self.max_usable_quote_amount_y),
            "step_constant_k": str(self.step_constant_k),
            "credit": str(self.credit),
            "base_step_qty": str(self.base_step_qty),
            "task_start_time": str(self.task_start_time),
            "start_base_balance": str(self.start_base_balance),
            "start_quote_balance": str(self.start_quote_balance),
            "bridge": str(self.bridge_symbol),
        }

    def create_stats_message(self):
        stats = {
            "time": str(datetime.now().time()),
            "runtime": str((datetime.now() - self.task_start_time).total_seconds()),
            "theo_buy": str(self.theo_buy),
            "theo_sell": str(self.theo_sell),
            "theo_last_updated": str(self.theo_last_updated.time()),
            "pnl": str(self.pnl),
            "max_pnl": str(self.max_pnl),
            "base_balance": str(self.pair.base.balance),
            "quote_balance": str(self.pair.quote.balance),
            # "remaining_usable_quote_balance": str(self.remaining_usable_quote_balance),
            "current_step": str(self.current_step),
            "orders": len(self.orders),
            "best_ask": str(self.best_seller),
            "best_bid": str(self.best_buyer),
            "bid_ask_last_updated": str(self.bid_ask_last_updated.time()),
            "binance_seen": self.binance_book_ticker_stream_seen,
            "btc_seen": self.btc_books_seen,
            # "time_diff": self.time_diff,
            "bridge_quote": str(self.bridge_quote),
            "bridge_last_updated": str(self.bridge_last_updated),
            "start_parameters": self.params_message,
        }

        return stats

    def broadcast_stats(self):
        message = self.create_stats_message()

        if debug:
            logger.info({k: message[k] for k in self.debug_keys})

        pub.publish_stats(self.channnel, message)

    async def broadcast_stats_periodical(self):
        while True:
            self.broadcast_stats()
            await asyncio.sleep(0.2)
