from dataclasses import dataclass
from typing import Optional

from src.domain import Asset, AssetPair
from src.exchanges.btcturk.base import BtcturkBase
from src.exchanges.btcturk.testnet.dummy import BtcturkDummy
from src.monitoring import logger


@dataclass
class BtcturkApiClientTestnet(BtcturkBase):
    name: str = "btcturk_testnet"

    dummy_exchange: BtcturkDummy = BtcturkDummy()

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> Optional[dict]:
        try:
            res = await self.dummy_exchange.mock_submit_limit_order(
                pair=pair,
                order_type=order_type,
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
