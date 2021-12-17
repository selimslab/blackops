import asyncio
from dataclasses import dataclass
from typing import List, Optional

from blackops.util.logger import logger

from .base import BtcturkBase
from .dummy import BtcturkDummy


@dataclass
class BtcturkApiClientTestnet(BtcturkBase):
    name: str = "btcturk_testnet"

    test_exchange: BtcturkDummy = BtcturkDummy()

    async def submit_limit_order(
        self, pair_symbol: str, order_type: str, price: float, quantity: float
    ):
        try:
            await self.test_exchange.process_limit_order(
                pair_symbol=pair_symbol,
                order_type=order_type,
                price=price,
                quantity=quantity,
            )
        except Exception as e:
            logger.error(e)
            raise e

    async def get_account_balance(self, assets: Optional[List[str]] = None):
        await asyncio.sleep(0.7)  # 90 per min, rate limit
        return await self.test_exchange.get_account_balance(assets)
