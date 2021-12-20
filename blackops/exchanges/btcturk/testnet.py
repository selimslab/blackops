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

    test_exchange: BtcturkDummy = BtcturkDummy()

    async def submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ):
        try:
            return await self.test_exchange.process_limit_order(
                pair=pair,
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


async def test_submit_limit_order():
    client = BtcturkApiClientTestnet()
    res = await client.submit_limit_order(
        pair=AssetPair(base=Asset("BTC"), quote=Asset("USD")),
        order_type="buy",
        price=0.000001,
        quantity=100,
    )

    print(res)
    assert res["success"] is False

    client.test_exchange.add_balance("TRY", Decimal("2000"))

    res = await client.submit_limit_order(
        pair=AssetPair(base=Asset("USDT"), quote=Asset("TRY")),
        order_type="buy",
        price=16.42,
        quantity=100,
    )
    print(res)
    assert res["success"] is True

    res = await client.get_account_balance()
    print(res)
    expected = {
        "TRY": {"free": Decimal("355.044399999999829162788956"), "locked": 0},
        "USDT": {"free": Decimal("100"), "locked": 0},
    }
    assert res == expected


if __name__ == "__main__":
    asyncio.run(test_submit_limit_order())
