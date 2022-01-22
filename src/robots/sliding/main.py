import asyncio
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from src.domain import OrderType, create_asset_pair
from src.environment import sleep_seconds
from src.monitoring import logger
from src.numberops import round_decimal_floor, round_decimal_half_up
from src.periodic import periodic
from src.pubsub import create_book_consumer_generator
from src.pubsub.pubs import BalancePub, BookPub
from src.robots.base import RobotBase
from src.robots.sliding.orders import OrderApi
from src.stgs.sliding.config import LeaderFollowerConfig

from .decision import DecisionAPI
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
    current_step: Decimal = Decimal(0)

    price_api: PriceAPI = field(default_factory=PriceAPI)
    decision_api: DecisionAPI = field(default_factory=DecisionAPI)
    stats: Stats = field(default_factory=Stats)

    def __post_init__(self) -> None:
        self.pair = create_asset_pair(self.config.input.base, self.config.input.quote)

        self.decision_api.set_credits(self.config)

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
                self.order_api.cancel_open_orders,
                sleep_seconds.cancel_open_orders,
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

        await self.decide(mid)

    async def decide(self, mid: Decimal) -> None:
        if not self.base_step_qty:
            return

        ask = self.price_api.follower.ask
        bid = self.price_api.follower.bid

        if not ask:
            return

        if not bid:
            return

        if not self.base_step_qty:
            return

        self.current_step = self.pair.base.free / self.base_step_qty
        credits = self.decision_api.get_credits(self.current_step)

        signals = self.decision_api.get_signals(mid, ask, bid, credits)
        prices = self.decision_api.get_target_prices(mid, ask, bid, credits)

        self.stats.credits = credits
        self.stats.signals = signals
        self.stats.prices = prices

        if not prices.taker:
            return

        if signals.sell >= 1:
            qty = self.base_step_qty * signals.sell
            if qty > self.pair.base.free:
                qty = round_decimal_floor(self.pair.base.free)

            if self.order_api.can_sell(prices.taker.sell, qty):
                await self.order_api.send_order(
                    OrderType.SELL, prices.taker.sell, int(qty)
                )

        elif signals.buy >= 1:
            qty = self.base_step_qty * signals.buy

            remaining_steps = self.config.max_step - self.current_step
            max_buyable = remaining_steps * self.base_step_qty
            if qty > max_buyable:
                qty = round_decimal_floor(max_buyable)

            if self.order_api.can_buy(prices.taker.buy, qty):
                await self.order_api.send_order(
                    OrderType.BUY, prices.taker.buy, int(qty)
                )

    async def close(self) -> None:
        await self.order_api.cancel_open_orders()

    def create_stats_message(self) -> dict:
        return {
            "start time": self.stats.start_time,
            "base credits": asdict(self.decision_api.credits),
            "current step": asdict(self.current_step),
            "current credits": asdict(self.stats.credits),
            "signals": asdict(self.stats.signals),
            "prices": {
                "market": asdict(self.price_api.follower),
                "target": asdict(self.stats.prices),
                "bridge": self.price_api.bridge,
            },
            "order": {
                "fresh": self.order_api.open_orders_fresh,
                "stats": asdict(self.order_api.stats),
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
