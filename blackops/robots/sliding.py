import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any, AsyncGenerator, Optional

import simplejson as json  # type: ignore

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.environment import debug
from blackops.exchanges.base import ExchangeBase
from blackops.exchanges.btcturk.base import BtcturkBase
from blackops.robots.base import RobotBase
from blackops.robots.config import SlidingWindowConfig, StrategyType
from blackops.robots.stats import RobotStats
from blackops.util.logger import logger
from blackops.util.periodic import periodic

getcontext().prec = 6


@dataclass
class OrderRobot:

    config: SlidingWindowConfig

    exchange: ExchangeBase
    pair: AssetPair
    channnel: str

    # ORDERS
    buy_orders: list = field(default_factory=list)
    sell_orders: list = field(default_factory=list)

    long_in_progress: bool = False
    short_in_progress: bool = False

    open_sell_orders: list = field(default_factory=list)
    open_buy_orders: list = field(default_factory=list)

    open_sell_orders_base_amount: Decimal = Decimal("0")
    open_buy_orders_base_amount: Decimal = Decimal("0")

    def get_orders(self):
        return self.buy_orders + self.sell_orders

    async def watch_open_orders(self):
        try:
            open_orders: Optional[dict] = await self.exchange.get_open_orders(
                self.pair
            )
            if not open_orders:
                open_orders = {}

            (
                self.open_sell_orders,
                self.open_buy_orders,
            ) = self.exchange.parse_open_orders(open_orders)

            open_sell_orders_base_amount = sum(
                Decimal(ask.get("leftAmount", "0")) for ask in self.open_sell_orders
            )
            self.open_sell_orders_base_amount = Decimal(
                str(open_sell_orders_base_amount)
            )

            open_buy_orders_base_amount = sum(
                Decimal(bid.get("leftAmount", "0")) for bid in self.open_buy_orders
            )
            self.open_buy_orders_base_amount = Decimal(str(open_buy_orders_base_amount))

        except Exception as e:
            msg = f"watch_open_orders: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)


    async def cancel_all_open_orders(self):
        try:
            if self.open_sell_orders or self.open_buy_orders:
                await self.exchange.cancel_multiple_orders(
                    self.open_sell_orders + self.open_buy_orders
                )
        except Exception as e:
            msg = f"cancel_all_open_orders: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)


    def cost_of_open_buy_orders(self, best_seller:Decimal):

        # we may not be able to buy from the best seller
        safety_margin = Decimal("1.01")
        if best_seller:
            return (
                self.open_buy_orders_base_amount  # 3 ETH
                * best_seller
                * self.exchange.buy_with_fee 
                * safety_margin
            )

        return Decimal("0")

    def approximate_gain_from_open_sell_orders(self, best_buyer:Decimal):
        if best_buyer:
            return (
                self.open_sell_orders_base_amount * best_buyer * self.exchange.sell_with_fee  
            )

        return Decimal("0")


    async def long(self, best_seller:Decimal):
        # we buy and sell at the quantized steps
        # so we buy or sell a quantum

        if not best_seller:
            return

        if self.long_in_progress:
            return

        price = float(best_seller)
        qty = float(self.config.base_step_qty)  #  we buy base

        try:
            self.long_in_progress = True

            order_log = await self.send_order("buy", price, qty)
            if order_log:
                self.buy_orders.append(order_log)
        except Exception as e:
            msg = f"long: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)

        finally:
            self.long_in_progress = False

    async def short(self, best_buyer:Decimal):
        if not best_buyer or not self.config.base_step_qty:
            return

        if self.short_in_progress:
            return

        price = float(best_buyer)
        qty = float(self.config.base_step_qty)  # we sell base

        try:
            self.short_in_progress = True
            order_log = await self.send_order("sell", price, qty)
            if order_log:
                self.sell_orders.append(order_log)
            res["theo"] = theo

        except Exception as e:
            msg = f"short: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)

        finally:
            self.short_in_progress = False


    async def send_order(self, side, price, qty):
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
                msg = f"could not {side} {qty} {self.pair.base.symbol} for {price}, response: {res}"
                raise Exception(msg)

            return res

        except Exception as e:
            msg = f"send_order: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)


@dataclass 
class FollowerRobot:
    exchange: ExchangeBase
    book_stream: AsyncGenerator
    books_seen: int = 0

    async def watch_follower(self):
        async for book in self.book_stream:
            if book:
                parsed_book = self.exchange.parse_book(book)
                self.update_follower_prices(parsed_book)
                self.books_seen += 1
            await asyncio.sleep(0)


    def update_follower_prices(self, book: dict):
        if not book:
            return
        try:
            best_ask = self.exchange.get_best_ask(book)
            if best_ask:
                self.best_seller = best_ask

            best_bid = self.exchange.get_best_bid(book)
            if best_bid:
                self.best_buyer = best_bid

            self.bid_ask_last_updated = datetime.now()

        except Exception as e:
            msg = f"update_follower_prices: {e}"
            logger.error(msg)
            pub.publish_error(self.channnel, msg)




@dataclass 
class TheoRobot:
    theo_buy: Optional[Decimal] = None
    theo_sell: Optional[Decimal] = None  # sell higher than theo_sell


    def calculate_window(self, book: dict) -> None:
        """Update theo_buy and theo_sell"""
        if not book:
            return

        try:
            mid = self.exchange.get_mid(book)

            if not mid:
                return

            mid = mid * self.bridge_quote


            step_size = self.config.step_constant_k * self.current_step

            mid -= step_size  # go down as you buy, we wish to buy lower as we buy

            self.theo_buy = mid - self.config.credit
            self.theo_sell = mid + self.config.credit

            self.theo_last_updated = datetime.now()
        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)


@dataclass 
class BridgeRobot:
    bridge_quote: Decimal = Decimal("1")

    async def watch_bridge(self):
        if not self.leader_bridge_quote_stream:
            raise ValueError("No bridge quote stream")

        async for book in self.leader_bridge_quote_stream:
            new_quote = self.leader_exchange.get_mid(book)
            if new_quote:
                self.bridge_quote = new_quote
                self.stats_robot.bridge_last_updated = datetime.now().time()
            await asyncio.sleep(0)


@dataclass 
class LeaderRobot:
    exchange: ExchangeBase
    book_stream: AsyncGenerator
    books_seen: int = 0

    async def update_theo(self):
        async for book in self.book_stream:
            if book:
                self.books_seen += 1
                self.calculate_window(book)
                await self.should_transact()
            await asyncio.sleep(0)


@dataclass
class BalanceRobot:
    exchange: ExchangeBase
    pair: AssetPair
    channnel: str

    start_base_balance:Decimal = Decimal("0")
    start_quote_balance:Decimal = Decimal("0")

    async def get_current_step(self):
       return self.pair.base.balance / self.config.base_step_qty

    async def update_balances(self):
        try:
            res: Optional[dict] = await self.exchange.get_account_balance()
            if not res:
                return

            balances = self.exchange.parse_account_balance(
                res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
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
            msg = f"update_balances: {e}"
            logger.error(msg)
            pub.publish_error(self.channel, msg)



@dataclass
class DecisionRobot:
    config: SlidingWindowConfig

    order_robot : OrderRobot
    balance_robot : BalanceRobot

    current_step: Decimal = Decimal("0")


    async def should_transact(self, theo_buy, best_seller, theo_sell, best_buyer):
        if self.should_long():
            await self.order_robot.long(best_seller)

        if self.should_short():
            await self.order_robot.short(best_buyer)

    def should_long(self, theo_buy, best_seller,):
        # we don't enforce max_usable_quote_amount_y too strict
        # we assume no deposits to quote during the task run
        approximate_buy_cost = 
        return (
            best_seller
            and theo_buy
            and best_seller <= theo_buy
            and self.usable_balance_to_buy() >= approximate_buy_cost
            and self.used_quote_amount() + approximate_buy_cost
            <= self.config.max_usable_quote_amount_y
        )

    def should_short(self):
        #  act only when you are ahead
        return (
            self.best_buyer
            and self.theo_sell
            and self.best_buyer >= self.theo_sell
            and self.pair.base.balance
            and self.usable_balance_to_sell() >= self.config.base_step_qty
        )

    def calculate_approximate_buy_cost(self, best_seller):
        return best_seller * self.config.base_step_qty * self..buy_with_fee  # type: ignore


    def used_quote_amount(self) -> Decimal:
        """Its still an approximation, but it's better than nothing"""
        total_used = Decimal("0")
        used_quote = self.balance_robot.start_quote_balance - self.balance_robot.pair.quote.balance
        total_used += used_quote
        if self.follower_robot.best_seller:
            total_used += self.order_robot.cost_of_open_buy_orders(self.follower_robot.best_seller)
        if self.follower_robot.best_buyer:
            total_used -= self.order_robot.approximate_gain_from_open_sell_orders(self.follower_robot.best_buyer)
        return total_used

    def usable_balance_to_buy(self) -> Decimal:
        if self.follower_robot.best_seller:
            return self.balance_robot.pair.quote.balance - self.order_robot.cost_of_open_buy_orders(self.follower_robot.best_seller)
        else:
            return self.balance_robot.pair.quote.balance

    def usable_balance_to_sell(self) -> Decimal:
        return self.balance_robot.pair.quote.balance - self.order_robot.open_sell_orders_base_amount



@dataclass
class SlidingWindowTrader(RobotBase):
    """
    Make decisions and send orders 
    """
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



    def __post_init__(self):
        self.channnel = self.config.sha
        self.order_robot = OrderRobot(config=self.config,exchange=self.follower_exchange, pair=self.pair, channnel=self.channnel)
        self.balance_robot = BalanceRobot(exchange=self.follower_exchange, pair=self.pair, channnel=self.channnel)
        self.decision_robot = DecisionRobot(order_robot=OrderRobot,
                            balance_robot=BalanceRobot,
                            config=self.config,
                                            )
        self.leader_robot= LeaderRobot(exchange=self.leader_exchange, pair=self.pair, channnel=self.channnel)

    def get_orders(self):
        return self.order_robot.get_orders()

    async def run(self):
        self.stats_robot.task_start_time = datetime.now()
        # this first call to read balances must be succesful or we exit
        await self.balance_robot.update_balances()
        self.start_base_balance = self.pair.base.balance
        self.start_quote_balance = self.pair.quote.balance

        await self.run_streams()

    async def run_streams(self):
        logger.info(
            f"Start streams for {self.config.type.name} with config {self.config}"
        )

        coroutines: Any = [
            self.watch_leader(),
            self.watch_follower(),
            periodic(self.balance_robot.update_balances, 0.72),
            periodic(self.order_robot.watch_open_orders, 0.3),
            periodic(self.order_robot.cancel_all_open_orders, 0.6),
            periodic(self.stats_robot.update_pnl, 1),
            periodic(self.stats_robot.broadcast_stats, 0.5),
        ]  # is this ordering important ?
        if self.config.bridge:
            coroutines.append(self.watch_bridge())

        await asyncio.gather(*coroutines)


    async def close(self):
        await self.order_robot.cancel_all_open_orders()


@dataclass
class StatsRobot(RobotStats):

    theo_last_updated: datetime = datetime.now()
    bid_ask_last_updated: datetime = datetime.now()
    bridge_last_updated: Optional[Any] = None

    binance_book_ticker_stream_seen: int = 0
    btc_books_seen: int = 0

    def __post_init__(self):
        self.config_dict = self.robot.config.dict()

    async def broadcast_stats(self):
        message = self.create_stats_message()

        message = json.dumps(message, default=str)

        pub.publish_stats(self.robot.channnel, message)

    async def calculate_pnl(self) -> Optional[Decimal]:
        try:
            if self.robot.pair.base.balance is None or self.robot.best_buyer is None:
                return None

            approximate_sales_gain: Decimal = (
                self.robot.pair.base.balance
                * self.robot.best_buyer
                * self.robot.follower_exchange.sell_with_fee  # type: ignore
            )

            return (
                self.robot.pair.quote.balance
                - self.robot.start_quote_balance
                + approximate_sales_gain
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
                "open_buy_orders": self.robot.open_buy_orders,
                "open_sell_orders": self.robot.open_sell_orders,
                "buy_orders": self.robot.buy_orders,
                "sell_orders": self.robot.sell_orders,
            },
            "config": self.config_dict,
        }

        return stats
