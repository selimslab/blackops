import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.btcturk.base import BtcturkBase
from blackops.exchanges.btcturk.dummy import BtcturkDummy
from blackops.util.logger import logger


@dataclass
class BtcturkApiClientTestnet(BtcturkBase):
    name: str = "btcturk_testnet"

    dummy_exchange: BtcturkDummy = BtcturkDummy()

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> dict:
        try:
            res = await self.dummy_exchange._submit_limit_order(
                pair=pair,
                order_type=order_type,
                price=price,
                quantity=quantity,
            )
            return res.dict()
        except Exception as e:
            logger.error(e)
            raise e

    async def get_open_orders(self, pair: AssetPair) -> dict:
        res = await self.dummy_exchange.get_open_orders(pair)
        return res.dict()

    async def _get_account_balance(self):
        res = await self.dummy_exchange.mock_account_balance()
        return res.dict()
