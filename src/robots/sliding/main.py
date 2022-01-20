import asyncio
import collections
import decimal
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Tuple

import src.pubsub.log_pub as log_pub
from src.domain import BPS, OrderType, create_asset_pair, maker_fee_bps, taker_fee_bps
from src.domain.models import AssetPair, AssetSymbol
from src.environment import sleep_seconds
from src.exchanges.locks import Locks
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import StopwatchAPI, periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.config import LeaderFollowerConfig
from src.robots.sliding.orders import OrderApi


@dataclass
class Credits:
    maker_bps: Decimal = Decimal(0)
    taker_bps: Decimal = Decimal(0)
    step_bps: Decimal = Decimal(0)


@dataclass
class FollowerPrices:
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None


@dataclass
class LeaderPrices:
    mids: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=10)
    )


@dataclass
class Stopwatches:
    leader: StopwatchAPI = field(default_factory=StopwatchAPI)
    follower: StopwatchAPI = field(default_factory=StopwatchAPI)
    bridge: StopwatchAPI = field(default_factory=StopwatchAPI)
    balance: StopwatchAPI = field(default_factory=StopwatchAPI)


@dataclass
class Prices:
    leader: LeaderPrices = field(default_factory=LeaderPrices)
    follower: FollowerPrices = field(default_factory=FollowerPrices)
    bridge: Optional[Decimal] = None


@dataclass
class PriceAPI:
    prices: Prices = field(default_factory=Prices)
    stopwatches: Stopwatches = field(default_factory=Stopwatches)

    def add_leader_mid(self, mid: Decimal, use_bridge=True) -> None:
        if use_bridge:
            if self.prices.bridge:
                mid *= self.prices.bridge
            else:
                return None

        self.prices.leader.mids.append(mid)

    def get_leader_median_mid(self) -> Optional[Decimal]:
        if self.prices.leader.mids:
            return statistics.median(self.prices.leader.mids)
        return None

    async def update_follower_prices(self, bid: Decimal, ask: Decimal) -> None:

        async with self.stopwatches.follower.stopwatch(
            self.clear_follower_prices, sleep_seconds.clear_prices
        ):
            self.prices.follower = FollowerPrices(ask=ask, bid=bid)

        await asyncio.sleep(0)

    def clear_follower_prices(self):
        self.prices.follower = FollowerPrices()

    def get_follower_ask(self):
        return self.prices.follower.ask

    def get_follower_bid(self):
        return self.prices.follower.bid

    async def update_bridge(self, quote: Decimal):
        async with self.stopwatches.bridge.stopwatch(
            self.clear_bridge, sleep_seconds.clear_prices
        ):
            self.prices.bridge = quote

    def clear_bridge(self):
        self.prices.bridge = None


@dataclass
class DecisionAPI:
    pass


class BalanceAPI:
    def init_pair(self, base: AssetSymbol, quote: AssetSymbol) -> None:
        self.pair = create_asset_pair(base, quote)

    def update_balances(self, balances: dict) -> None:
        base_balances: dict = balances[self.pair.base.symbol]
        self.pair.base.free = Decimal(base_balances["free"])
        self.pair.base.locked = Decimal(base_balances["locked"])

        quote_balances: dict = balances[self.pair.quote.symbol]
        self.pair.quote.free = Decimal(quote_balances["free"])
        self.pair.quote.locked = Decimal(quote_balances["locked"])

    def add_base_qty(self, qty):
        self.pair.base.free += qty

    def remove_base_qty(self, qty):
        self.pair.base.free -= qty


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    current_step: Decimal = Decimal("0")

    start_time: datetime = field(default_factory=lambda: datetime.now())

    credits: Credits = field(default_factory=Credits)

    price_api: PriceAPI = field(default_factory=PriceAPI)
    balance_api: BalanceAPI = field(default_factory=BalanceAPI)

    locks: Locks = field(default_factory=Locks)

    # SETUP

    def __post_init__(self) -> None:
        self.set_credits()
        self.balance_api.init_pair(self.config.input.base, self.config.input.quote)

        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

        self.order_api = OrderApi(
            config=self.config,
            pair=create_asset_pair(self.config.input.base, self.config.input.quote),
            exchange=self.follower_pub.api_client,
        )

    def set_credits(self):
        try:
            self.credits.maker_bps = (
                ((maker_fee_bps + taker_fee_bps) / Decimal(2)) + self.config.margin_bps
            ) * BPS

            self.credits.taker_bps = (taker_fee_bps + self.config.margin_bps) * BPS
            self.credits.step_bps = (
                self.credits.taker_bps / self.config.max_step
            ) * BPS
        except Exception as e:
            logger.error(e)
            raise e

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

    # LEADER
    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            if book:
                mid = self.leader_pub.api_client.get_mid(book)
                if mid:
                    self.price_api.add_leader_mid(mid, self.config.input.use_bridge)

    # FOLLOWER

    async def consume_follower_pub(self) -> None:
        gen = create_book_consumer_generator(self.follower_pub)
        async for book in gen:
            ask = self.follower_pub.api_client.get_best_ask(book)
            bid = self.follower_pub.api_client.get_best_bid(book)
            if bid and ask:
                await self.price_api.update_follower_prices(bid, ask)
                await self.should_transact()

    # BALANCE

    async def update_balances(self) -> None:
        try:
            res: Optional[dict] = self.balance_pub.balances
            if not res:
                return

            balances = self.follower_pub.api_client.parse_account_balance(
                res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
            )
            if balances:
                self.balance_api.update_balances(balances)
        except Exception as e:
            msg = f"update_balances: {e}"
            logger.error(msg)
            log_pub.publish_error(message=msg)
            raise e

    # BRIDGE

    async def consume_bridge_pub(self) -> None:
        if not self.bridge_pub:
            raise Exception("no bridge_pub")

        gen = create_book_consumer_generator(self.bridge_pub)
        async for book in gen:
            quote = self.bridge_pub.api_client.get_mid(book)
            if quote:
                await self.price_api.update_bridge(quote)

    # DECIDE
    async def should_transact(self) -> None:
        leader_price = self.price_api.get_leader_median_mid()
        if not leader_price:
            return

        bid = self.price_api.get_follower_bid()
        if bid:
            await self.should_sell(leader_price, bid)

        ask = self.price_api.get_follower_ask()
        if ask:
            await self.should_buy(leader_price, ask)

    async def should_sell(self, leader_price: Decimal, bid: Decimal) -> None:
        sell_signal = self.get_sell_signal(leader_price, bid)
        if sell_signal and sell_signal >= 1:
            qty = (self.config.quote_step_qty / bid) * self.config.sell_to_buy_ratio
            qty = round_decimal_half_up(qty)
            await self.sell(bid, qty)

    async def should_buy(self, leader_price: Decimal, ask: Decimal) -> None:
        buy_signal = self.get_buy_signal(leader_price, ask)
        if buy_signal and buy_signal >= 1:
            qty = self.config.quote_step_qty / ask
            qty = round_decimal_half_up(qty)
            await self.buy(ask, qty)

    def get_step_risk_bps(self):
        """Step risk makes buy signal weaker, and sell signal stronger"""
        return self.credits.step_bps * self.current_step

    def get_signal_threshold(self):
        return self.credits.taker_bps + self.get_step_risk_bps()

    def get_buy_signal(self, leader_mid, ask):
        min_signal = self.get_signal_threshold() * ask
        return (leader_mid - ask) / min_signal

    def get_sell_signal(self, leader_mid, bid):
        min_signal = self.get_signal_threshold() * bid
        return (bid - leader_mid) / min_signal

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

    def update_step(self, price: Decimal) -> None:
        self.current_step = self.pair.base.free * price / self.config.quote_step_qty

    def step_ok(self, price):
        self.update_step(price)
        return self.current_step <= self.config.max_step

    def can_buy(self, price, qty) -> bool:
        return (
            bool(self.pair.quote.free)
            and self.pair.quote.free >= price * qty
            and self.step_ok(price)
        )

    async def buy(self, price: Decimal, qty: Decimal):
        if not self.can_buy(price, qty):
            return None

        order_log = await self.order_api.send_order(OrderType.BUY, price, qty)

        if order_log:
            self.buy_delivered(qty)

    async def sell(self, price: Decimal, qty: Decimal):
        if not self.pair.base.free:
            return None

        if self.pair.base.free < qty:
            if self.pair.base.free * price < self.config.minimum_sell_qty:
                return None
            else:
                qty = round_decimal_floor(self.pair.base.free)

        order_id = await self.order_api.send_order(OrderType.SELL, price, qty)

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
            "prices": asdict(self.price_api.prices),
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

    #     ask = self.follower.follower_prices.ask

    #     if (
    #         ask
    #         and self.targets.taker.buy
    #         and self.targets.maker.buy
    #         and self.targets.taker.buy < ask <= self.targets.maker.buy
    #     ):
    #         return one_bps_lower(ask)

    #     return None

    # def get_short_price_maker(self) -> Optional[Decimal]:
    #     bid = self.follower.follower_prices.bid

    #     if (
    #         bid
    #         and self.targets.taker.sell
    #         and self.targets.maker.sell
    #         and self.targets.maker.sell <= bid < self.targets.taker.sell
    #     ):
    #         return one_bps_higher(bid)

    #     return None
