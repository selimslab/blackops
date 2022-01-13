from dataclasses import dataclass, field
from typing import Optional

from src.domain import Asset, AssetPair
from src.domain.models import OrderType
from src.environment import sleep_seconds
from src.exchanges.btcturk.base import BtcturkBase
from src.exchanges.btcturk.testnet.dummy import BtcturkDummy
from src.monitoring import logger
from src.periodic import StopwatchContext, timer_lock


@dataclass
class BtcturkApiClientTestnet(BtcturkBase):
    name: str = "btcturk_testnet"

    dummy_exchange: BtcturkDummy = field(default_factory=BtcturkDummy)

    async def submit_limit_order(
        self, pair: AssetPair, side: OrderType, price: float, quantity: float
    ) -> Optional[dict]:
        try:
            if side == OrderType.BUY:
                lock = self.locks.buy
                wait = sleep_seconds.ex_buy
            else:
                lock = self.locks.sell
                wait = sleep_seconds.ex_sell

            if lock.locked():
                return None

            async with timer_lock(lock, wait):
                res = await self.dummy_exchange.mock_submit_limit_order(
                    pair=pair,
                    order_type=side.value,
                    price=price,
                    quantity=quantity,
                )
                return res.dict()
        except Exception as e:
            logger.error(f"submit_limit_order: {e}")
            raise e

    async def get_open_orders(self, pair: AssetPair) -> dict:
        res = await self.dummy_exchange.mock_get_open_orders(pair)
        return res.dict()

    async def get_account_balance(self):
        res = await self.dummy_exchange.mock_account_balance()
        return res.dict()
