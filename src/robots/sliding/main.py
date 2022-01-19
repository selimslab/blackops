import asyncio
import decimal
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Tuple

import src.pubsub.log_pub as log_pub
from src.domain import BPS, OrderType, create_asset_pair, maker_fee_bps, taker_fee_bps
from src.environment import sleep_seconds
from src.exchanges.locks import Locks
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import StopwatchAPI, periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.config import SlidingWindowConfig
from src.robots.sliding.orders import OrderApi


@dataclass
class Credits:
    maker: Decimal = Decimal(0)
    taker: Decimal = Decimal(0)
    step: Decimal = Decimal(0)


@dataclass
class MarketPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class TargetPrices:
    buy: Optional[Decimal] = None
    sell: Optional[Decimal] = None


@dataclass
class Window:
    mid: Optional[Decimal] = None
    bridge: Optional[Decimal] = None
    maker: TargetPrices = field(default_factory=TargetPrices)
    taker: TargetPrices = field(default_factory=TargetPrices)


@dataclass
class Stopwatches:
    leader: StopwatchAPI = field(default_factory=StopwatchAPI)
    follower: StopwatchAPI = field(default_factory=StopwatchAPI)
    bridge: StopwatchAPI = field(default_factory=StopwatchAPI)
    balance: StopwatchAPI = field(default_factory=StopwatchAPI)


@dataclass
class SlidingWindowTrader(RobotBase):
    config: SlidingWindowConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    base_step_qty: Decimal = Decimal("0")
    current_step: Decimal = Decimal("0")

    targets: Window = field(default_factory=Window)

    stopwatches: Stopwatches = field(default_factory=Stopwatches)

    start_time: datetime = field(default_factory=lambda: datetime.now())

    credits: Credits = Credits()

    prices: MarketPrices = field(default_factory=MarketPrices)

    locks: Locks = field(default_factory=Locks)

    # SETUP

    def __post_init__(self) -> None:
        self.set_credits()
        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

        self.order_api = OrderApi(
            config=self.config,
            pair=create_asset_pair(self.config.input.base, self.config.input.quote),
            exchange=self.follower_pub.api_client,
        )

    def set_credits(self):
        try:
            self.credits.maker = (
                (maker_fee_bps + taker_fee_bps) / Decimal(2)
            ) + self.config.margin_bps
            self.credits.taker = taker_fee_bps + self.config.margin_bps
            self.credits.step = self.credits.taker / self.config.max_step
        except Exception as e:
            logger.error(e)
            raise e

    def set_base_step_qty(self, price: Decimal) -> None:
        self.base_step_qty = round_decimal_half_up(self.config.quote_step_qty / price)

    # RUN

    async def run(self) -> None:
        logger.info(f"Starting {self.config.sha}..")
        await self.run_streams()

    async def run_streams(self) -> None:
        aws: Any = [
            self.consume_leader_pub(),
            self.consume_follower_pub(),
            periodic(
                self.update_balances,
                sleep_seconds.poll_balance_update,
            ),
            periodic(
                self.order_api.refresh_open_orders,
                sleep_seconds.refresh_open_orders,
            ),
            periodic(
                self.order_api.cancel_open_orders,
                sleep_seconds.cancel_open_orders,
            ),
        ]

        if self.bridge_pub:
            aws.append(self.consume_bridge_pub())

        await asyncio.gather(*aws)

    # DECISION

    async def should_transact(self) -> None:
        await self.should_sell()
        await self.should_buy()

    async def should_sell(self) -> None:
        res = self.get_taker_short()
        if res:
            price, qty = res
            await self.sell(price, qty)

    def step_ok(self):
        return self.current_step <= self.config.max_step

    async def should_buy(self) -> None:
        if not self.step_ok():
            return None

        res = self.get_taker_long()
        if res:
            price, qty = res
            await self.buy(price, qty)

    def update_step(self):
        if not self.base_step_qty:
            return
        self.current_step = self.pair.base.free / self.base_step_qty

    def get_taker_long(self) -> Optional[Tuple[Decimal, Decimal]]:
        ask = self.prices.ask
        buy = self.targets.taker.buy
        if ask and buy and ask <= buy:
            qty = buy / ask * self.base_step_qty
            return buy, round_decimal_floor(qty)
        return None

    def get_taker_short(self) -> Optional[Tuple[Decimal, Decimal]]:
        bid = self.prices.bid
        sell = self.targets.taker.sell
        if bid and sell and bid >= sell:
            qty = bid / sell * self.base_step_qty * self.config.sell_to_buy_ratio
            return bid, round_decimal_floor(qty)
        return None

    # LEADER

    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            await self.update_window(book)

    async def update_window(self, book: dict) -> None:
        try:
            mid = self.get_window_mid(book)
            if not mid:
                return None

            if not self.base_step_qty:
                self.set_base_step_qty(mid)

            self.update_step()

            slide_down = self.credits.step * self.current_step * mid * BPS

            mid -= slide_down

            taker_credit = self.credits.taker * mid * BPS

            async with self.stopwatches.leader.stopwatch(
                self.clear_targets, sleep_seconds.clear_prices
            ):
                self.targets.taker.buy = mid - taker_credit
                self.targets.taker.sell = mid + taker_credit

        except Exception as e:
            msg = f"calculate_window: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)

    def get_window_mid(self, book: dict) -> Optional[Decimal]:
        if not book:
            return None
        try:
            leader_mid = self.leader_pub.api_client.get_mid(book)

            self.targets.mid = leader_mid
            if not leader_mid:
                return None

            if self.config.input.use_bridge:
                if self.targets.bridge:
                    return leader_mid * self.targets.bridge
                return None
            else:
                return leader_mid

        except Exception as e:
            msg = f"get_window_mid: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            return None

    def clear_targets(self):
        self.targets = Window()

    # FOLLOWER

    async def consume_follower_pub(self) -> None:
        gen = create_book_consumer_generator(self.follower_pub)
        async for book in gen:
            await self.update_follower_prices(book)
            await self.should_transact()

    async def update_follower_prices(self, book) -> None:
        try:
            ask = self.follower_pub.api_client.get_best_ask(book)
            bid = self.follower_pub.api_client.get_best_bid(book)
            if ask and bid:
                async with self.stopwatches.follower.stopwatch(
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
        self.prices.ask = None
        self.prices.bid = None

    # BRIDGE

    async def consume_bridge_pub(self) -> None:
        if not self.bridge_pub:
            raise Exception("no bridge_pub")

        gen = create_book_consumer_generator(self.bridge_pub)
        async for book in gen:
            mid = self.bridge_pub.api_client.get_mid(book)
            if mid:
                async with self.stopwatches.bridge.stopwatch(
                    self.clear_bridge, sleep_seconds.clear_prices
                ):
                    self.targets.bridge = mid

    def clear_bridge(self):
        self.targets.bridge = None

    # BALANCE

    def clear_balance(self):
        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

    async def update_balances(self) -> None:
        try:
            res: Optional[dict] = self.balance_pub.balances
            if not res:
                return

            balances = self.follower_pub.api_client.parse_account_balance(
                res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
            )

            async with self.stopwatches.balance.stopwatch(
                self.clear_balance, sleep_seconds.clear_balance
            ):
                base_balances: dict = balances[self.pair.base.symbol]
                self.pair.base.free = Decimal(base_balances["free"])
                self.pair.base.locked = Decimal(base_balances["locked"])

                quote_balances: dict = balances[self.pair.quote.symbol]
                self.pair.quote.free = Decimal(quote_balances["free"])
                self.pair.quote.locked = Decimal(quote_balances["locked"])

        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            raise e

    # ORDER

    def get_order_lock(self, side):
        return self.locks.buy if side == OrderType.BUY else self.locks.sell

    def get_precise_price(self, price: Decimal, reference: Decimal) -> Decimal:
        return price.quantize(reference, rounding=decimal.ROUND_DOWN)

    def buy_delivered(self, qty):
        # reflect it in balance until the new one
        self.pair.base.free += qty

    def sell_delivered(self, qty):
        self.pair.base.free -= qty

    def can_buy(self, price, qty) -> bool:
        return bool(self.pair.quote.free) and self.pair.quote.free >= price * qty

    async def buy(self, price: Decimal, qty: Decimal):
        if not self.can_buy(price, qty):
            return None

        if not self.prices.ask:
            return None

        precise_price = self.get_precise_price(price, self.prices.ask)

        if self.locks.buy.locked():
            return None

        async with self.locks.buy:
            order_log = await self.order_api.send_order(
                OrderType.BUY, precise_price, qty
            )

            if order_log:
                self.buy_delivered(qty)

    async def sell(self, price: Decimal, qty: Decimal):
        if not self.pair.base.free or not self.prices.bid:
            return None

        if self.pair.base.free < qty:
            if self.pair.base.free * price < self.config.minimum_sell_qty:
                return None
            else:
                qty = round_decimal_floor(self.pair.base.free)

        precise_price = self.get_precise_price(price, self.prices.bid)

        if self.locks.sell.locked():
            return None

        async with self.locks.sell:
            order_id = await self.order_api.send_order(
                OrderType.SELL, precise_price, qty
            )

            if order_id:
                self.sell_delivered(qty)

    # STATS

    def create_stats_message(self) -> dict:
        return {
            "start time": self.start_time,
            "credits": asdict(self.credits),
            "order stats": asdict(self.order_api.stats),
            "open orders": list(self.order_api.open_order_ids),
            "cancelled orders": list(self.order_api.cancelled),
            "open_orders_fresh": self.order_api.open_orders_fresh,
            "targets": asdict(self.targets),
            "market": asdict(self.prices),
            "binance": {
                "last update": self.leader_pub.last_updated.time(),
                "books seen": self.leader_pub.books_seen,
            },
            "btc": {
                "last update": self.follower_pub.last_updated.time(),
                "books seen": self.follower_pub.books_seen,
            },
        }

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    # def get_long_price_maker(self) -> Optional[Decimal]:

    #     ask = self.follower.prices.ask

    #     if (
    #         ask
    #         and self.targets.taker.buy
    #         and self.targets.maker.buy
    #         and self.targets.taker.buy < ask <= self.targets.maker.buy
    #     ):
    #         return one_bps_lower(ask)

    #     return None

    # def get_short_price_maker(self) -> Optional[Decimal]:
    #     bid = self.follower.prices.bid

    #     if (
    #         bid
    #         and self.targets.taker.sell
    #         and self.targets.maker.sell
    #         and self.targets.maker.sell <= bid < self.targets.taker.sell
    #     ):
    #         return one_bps_higher(bid)

    #     return None
