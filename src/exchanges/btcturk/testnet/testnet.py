from dataclasses import dataclass, field
from typing import Optional

from src.domain import Asset, AssetPair
from src.domain.models import OrderType
from src.environment import sleep_seconds
from src.exchanges.btcturk.base import BtcturkBase
from src.exchanges.btcturk.testnet.dummy import BtcturkDummy
from src.monitoring import logger
from src.periodic import StopwatchAPI, lock_with_timeout


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
                wait = sleep_seconds.buy_wait
            else:
                lock = self.locks.sell
                wait = sleep_seconds.sell_wait

            async with lock_with_timeout(lock, wait) as ok:
                if ok:
                    res = await self.dummy_exchange.mock_submit_limit_order(
                        pair=pair,
                        order_type=side.value,
                        price=price,
                        quantity=quantity,
                    )
                    return res.dict()

            return None

        except Exception as e:
            logger.error(f"submit_limit_order: {e}")
            raise e

    async def get_open_orders(self, pair: AssetPair) -> dict:
        res = await self.dummy_exchange.mock_get_open_orders(pair)
        return res.dict()

    async def get_account_balance(self):
        res = await self.dummy_exchange.mock_account_balance()
        return res.dict()
