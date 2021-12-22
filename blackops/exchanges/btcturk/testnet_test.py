import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.btcturk.base import (
    AccountBalanceResponse,
    BtcturkBase,
    OpenOrdersData,
    OpenOrdersResponse,
    OrderData,
    OrderType,
    SubmitOrderResponse,
)
from blackops.exchanges.btcturk.dummy import BtcturkDummy
from blackops.util.logger import logger

from .testnet import BtcturkApiClientTestnet


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

    client.dummy_exchange.add_balance("TRY", Decimal("2000"))

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
