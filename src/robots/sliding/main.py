import asyncio
import collections
import statistics
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from src.domain import BPS, OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi
from src.stgs.sliding.config import LeaderFollowerConfig

from .prices import PriceAPI
from .stats import Stats


@dataclass
class LeaderFollowerTrader(RobotBase):
    config: LeaderFollowerConfig

    leader_pub: BookPub
    follower_pub: BookPub
    balance_pub: BalancePub
    bridge_pub: Optional[BookPub] = None

    base_step_qty: Optional[Decimal] = None

    price_api: PriceAPI = field(default_factory=PriceAPI)
    stats: Stats = field(default_factory=Stats)

    leader_mids: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=12)
    )

    sell_prices: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=5)
    )

    buy_prices: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=5)
    )

    buy_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=24)
    )

    sell_signals: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=16)
    )

    def __post_init__(self) -> None:
        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

        self.order_api = OrderApi(
            config=self.config,
            pair=self.pair,
            exchange=self.follower_pub.api_client,
        )

    def set_base_step_qty(self, price: Decimal) -> None:
        self.base_step_qty = round_decimal_half_up(self.config.quote_step_qty / price)

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
                self.order_api.clear_orders_in_last_second,
                0.95,
            ),
        ]

        if self.bridge_pub:
            aws.append(self.consume_bridge_pub())

        await asyncio.gather(*aws)

    # BALANCE

    async def update_balances(self) -> None:
        res: Optional[dict] = self.balance_pub.balances
        if not res:
            return

        balances = self.follower_pub.api_client.parse_account_balance(
            res, symbols=[self.pair.base.symbol, self.pair.quote.symbol]
        )
        base_balances: dict = balances[self.pair.base.symbol]
        self.pair.base.free = Decimal(base_balances["free"])
        self.pair.base.locked = Decimal(base_balances["locked"])

        quote_balances: dict = balances[self.pair.quote.symbol]
        self.pair.quote.free = Decimal(quote_balances["free"])
        self.pair.quote.locked = Decimal(quote_balances["locked"])

        self.order_api.open_order_qtys = {}

    # BRIDGE

    async def consume_bridge_pub(self) -> None:
        if not self.bridge_pub:
            raise Exception("no bridge_pub")

        gen = create_book_consumer_generator(self.bridge_pub)
        async for book in gen:
            if book:
                bridge = self.bridge_pub.api_client.get_mid(book)
                if bridge:
                    await self.price_api.update_bridge(bridge)

    # FOLLOWER

    async def consume_follower_pub(self) -> None:
        gen = create_book_consumer_generator(self.follower_pub)
        async for book in gen:
            if book:
                await self.update_follower_prices(book)

    async def update_follower_prices(self, book: dict) -> None:
        ask = self.follower_pub.api_client.get_best_ask(book)
        bid = self.follower_pub.api_client.get_best_bid(book)
        if ask and bid:

            if not self.base_step_qty:
                mid = (ask + bid) / Decimal(2)
                self.set_base_step_qty(mid)

            await self.price_api.update_follower_prices(ask, bid)

    # LEADER
    async def consume_leader_pub(self) -> None:
        gen = create_book_consumer_generator(self.leader_pub)
        async for book in gen:
            if book:
                await self.consume_leader_book(book)

    async def consume_leader_book(self, book: dict) -> None:
        mid = self.leader_pub.api_client.get_mid(book)
        if not mid:
            return

        mid = self.price_api.apply_bridge_to_price(mid, self.config.input.use_bridge)

        if not mid:
            return

        self.leader_mids.append(mid)

        await self.decide(mid)

    # DECIDE

    async def decide(self, mid: Decimal) -> None:
        if not self.base_step_qty:
            return

        # mid = self.get_risk_adjusted_mid(mid, current_step)

        median_mid = statistics.median(self.leader_mids)
        # price_mid = statistics.median(list(self.leader_mids)[-5:])

        bid = self.price_api.follower.bid
        if bid:
            await self.should_sell(mid, bid, median_mid)

        ask = self.price_api.follower.ask
        if ask:
            await self.should_buy(mid, ask, median_mid)

    def get_unit_sell_signal(self, mid: Decimal) -> Decimal:
        return self.config.credits.sell * mid * BPS

    def get_unit_buy_signal(self, mid: Decimal) -> Decimal:
        return self.config.credits.buy * mid * BPS

    # def get_risk_adjusted_mid(self, mid: Decimal, current_step: Decimal) -> Decimal:
    #     hold_risk = self.config.credits.step * current_step * mid * BPS
    #     return mid - hold_risk

    # SELL
    async def should_sell(
        self, mid: Decimal, bid: Decimal, median_mid: Decimal
    ) -> None:
        unit_sell_signal = self.get_unit_sell_signal(median_mid)
        signal = (bid - median_mid) / unit_sell_signal

        self.sell_signals.append(signal)
        signal = statistics.median(self.sell_signals)

        price = mid + unit_sell_signal
        self.sell_prices.append(price)
        price = statistics.median(self.sell_prices)

        self.stats.taker.sell = price
        self.stats.signals.sell = signal

        if not self.base_step_qty:
            return

        if signal >= 1:

            price = self.price_api.get_precise_price(price, bid)

            qty = self.base_step_qty * signal

            await self.sell(price, qty)

    async def sell(self, price, qty):
        # sell all
        if qty > self.pair.base.free:
            qty = round_decimal_floor(self.pair.base.free)

        qty = int(qty)

        if not self.order_api.can_sell(price, qty):
            return None

        await self.order_api.send_order(OrderType.SELL, price, qty)

    # BUY

    async def should_buy(self, mid: Decimal, ask: Decimal, median_mid: Decimal) -> None:

        if not self.base_step_qty:
            return

        current_step = self.pair.base.total_balance / self.base_step_qty
        remaining_step = self.config.max_step - current_step

        unit_buy_signal = self.get_unit_buy_signal(median_mid)
        signal = (median_mid - ask) / unit_buy_signal
        self.buy_signals.append(signal)
        signal = statistics.median(self.buy_signals)

        self.stats.signals.buy = signal

        price = mid - unit_buy_signal
        self.buy_prices.append(price)
        price = statistics.median(self.buy_prices)
        self.stats.taker.buy = price

        if remaining_step < 0.3:
            return

        if signal >= 1:
            price = self.price_api.get_precise_price(price, ask)
            qty = self.base_step_qty * signal
            max_buyable = remaining_step * self.base_step_qty
            if qty > max_buyable:
                qty = max_buyable
            await self.buy(price, qty)

    async def buy(self, price, qty):
        if not self.order_api.can_buy(price, qty):
            return

        qty = int(qty)
        await self.order_api.send_order(OrderType.BUY, price, qty)

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.stats.start_time,
            "step amount": self.config.quote_step_qty,
            "max_step": self.config.max_step,
            "order": {
                "fresh": self.order_api.open_orders_fresh,
                "stats": asdict(self.order_api.stats),
                "open qtys": self.order_api.open_order_qtys,
            },
            "prices": {
                "taker": asdict(self.stats.taker),
                "market": asdict(self.price_api.follower),
                "bridge": self.price_api.bridge,
                "signals": asdict(self.stats.signals),
            },
            "binance": {
                "last update": self.leader_pub.last_updated.time(),
                "books seen": self.leader_pub.books_seen,
            },
            "btc": {
                "last update": self.follower_pub.last_updated.time(),
                "books seen": self.follower_pub.books_seen,
            },
        }
