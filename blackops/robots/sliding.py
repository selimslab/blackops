import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, List, Optional

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.environment import is_prod
from blackops.exchanges.base import ExchangeBase
from blackops.robots.base import RobotBase
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

    # Internals

    name: str = "sliding_window"

    bridge_symbol: Optional[str] = None

    leader_bridge_quote_stream: Optional[AsyncGenerator] = None

    bridge_quote: Decimal = Decimal("1")

    bridge_last_updated: Optional[Any] = None

    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell

    best_seller: Optional[Decimal] = None
    best_buyer: Optional[Decimal] = None

    task_start_time: datetime = datetime.now()
    theo_last_updated: datetime = datetime.now()
    bid_ask_last_updated: datetime = datetime.now()
    time_diff: float = 0

    orders: dict = field(
        default_factory=dict
    )  # track your orders and figure out balance

    pnl: Decimal = Decimal("0")
    max_pnl: Decimal = Decimal("0")

    binance_book_ticker_stream_seen: int = 0
    btc_books_seen: int = 0

    start_quote_balance: Decimal = Decimal("0")
    start_base_balance: Decimal = Decimal("0")

    current_step: Decimal = Decimal("0")

    # remaining_usable_quote_balance: Decimal = Decimal("0")

    #  NOTES

    # if we don't have a manual step_size_constant, step_size_constant = mid *

    # if we don't have a manual credit, credit could be fee_percent *
    # Decimal(1.5)

    # fee_percent * Decimal(1.5)
    # Decimal(0.001)

    async def run(self):
        self.channnel = self.sha

        await self.update_base_balance()

        self.save_start_balances()

        self.broadcast_start_params()

        await self.run_streams()

    def save_start_balances(self):
        self.start_base_balance = self.pair.base.balance
        self.start_quote_balance = self.pair.quote.balance

        if self.max_usable_quote_amount_y < self.pair.quote.balance:
            msg = f"max_usable_quote_amount_y {self.max_usable_quote_amount_y} but quote_balance {self.pair.quote.balance}"

            pub.publish_error(self.channnel, msg)

            raise Exception(msg)

    def get_orders(self):
        return self.orders

    async def update_base_balance(self):
        try:
            balances: dict = await self.follower_exchange.get_account_balance(
                assets=[self.pair.base.symbol]
            )

            base_balances = balances[self.pair.base.symbol]
            self.pair.base.balance = Decimal(base_balances["free"]) + Decimal(
                base_balances["locked"]
            )

            # self.pair.quote.balance = balances[self.pair.quote.symbol]

        except Exception as e:
            msg = f"could not read balances: {e}"
            pub.publish_error(self.channnel, msg)
            raise Exception(msg)

    async def run_streams(self):
        logger.info(f"Start streams for {self.name}")

        consumers: Any = [
            self.watch_leader(),
            self.watch_follower(),
            self.broadcast_stats_periodical(),
            self.update_current_step_from_balances(),
        ]  # is this ordering important ?
        if self.bridge_symbol:
            consumers.append(self.watch_bridge())

        await asyncio.gather(*consumers)

    async def watch_leader(self):
        async for book in self.leader_book_ticker_stream:
            if book:
                self.calculate_window(book)
                await self.should_transact()
                self.binance_book_ticker_stream_seen += 1
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

    async def update_current_step_from_balances(self):
        # raises Exception if cant't read balance
        while True:
            try:
                await self.update_base_balance()
                self.current_step = (
                    self.pair.base.balance - self.start_base_balance
                ) / self.base_step_qty  # so we may have step 1.35 or so
            except Exception as e:
                logger.info(e)

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

    def should_long(self):
        #  act only when you are ahead
        # TODO we can just order theo and cancel later
        return self.best_seller and self.theo_buy and self.best_seller <= self.theo_buy

    def should_short(self):
        #  act only when you are ahead
        return self.best_buyer and self.theo_sell and self.best_buyer >= self.theo_sell

    async def long(self):
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum

        if not self.best_seller:
            return

        price = float(self.best_seller)
        qty = float(self.base_step_qty)  #  we buy base
        symbol = self.pair.symbol

        await self.send_order("long", price, qty, symbol)

    async def short(self):
        if not self.best_buyer or not self.base_step_qty:
            return

        price = float(self.best_buyer)
        qty = float(self.base_step_qty)  # we sell base
        symbol = self.pair.symbol

        await self.send_order("short", price, qty, symbol)

    async def send_order(self, side, price, qty, symbol):

        if side == "long":
            func = self.follower_exchange.long
            theo = self.theo_buy
        elif side == "short":
            func = self.follower_exchange.short
            theo = self.theo_sell
        else:
            raise Exception("invalid side")

        try:

            res = await func(price, qty, symbol)

            is_ok = res and res.get("success") and res.get("data")
            if not is_ok:
                msg = f"could not {side} {symbol} at {price} for {qty}: {res}"
                raise Exception(msg)

            data = res.get("data")

            ts = data.get("datetime")
            order_time = datetime.fromtimestamp(ts)

            order_id = data.get("id")
            self.orders[order_id] = data

            self.log_order(side, order_time, price, qty, theo)

            await self.update_pnl()

        except Exception as e:
            logger.info(e)
            pub.publish_message(self.channnel, str(e))

    # MONITORING

    def broadcast_start_params(self):
        self.params_message = self.create_params_message()
        pub.publish_params(self.channnel, self.params_message)
        logger.info(self.params_message)

    def log_order(self, side, order_time, price, qty, theo):
        order_log = {
            "type": side,
            "time": str(order_time),
            "price": str(price),
            "qty": str(qty),
            "theo": str(theo),
        }

        if is_prod:
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
            "name": self.name,
            "pair": self.pair.symbol,
            "max_usable_quote_amount_y": str(self.max_usable_quote_amount_y),
            "step_constant_k": str(self.step_constant_k),
            "credit": str(self.credit),
            "base_step_qty": str(self.base_step_qty),
            "task_start_time": str(self.task_start_time),
            "start_base_balance": str(self.start_base_balance),
            "start_quote_balance": str(self.start_quote_balance),
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
            "bridge": str(self.bridge_quote),
            "bridge_last_updated": str(self.bridge_last_updated),
        }
        if is_prod:
            stats["params"] = self.params_message

        return stats

    def broadcast_stats(self):
        message = self.create_stats_message()
        if is_prod:
            pub.publish_stats(self.channnel, message)
        else:
            keys = (
                "runtime",
                "base_balance",
                "quote_balance",
                "orders",
                "pnl",
                "max_pnl",
                "binance_seen",
                "btc_seen",
            )
            logger.info({k: message[k] for k in keys})

    async def broadcast_stats_periodical(self):
        while True:
            self.broadcast_stats()
            await asyncio.sleep(0.5)
