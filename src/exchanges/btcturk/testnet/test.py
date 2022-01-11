import asyncio
from decimal import Decimal

from src.domain import Asset, AssetPair, create_asset_pair
from src.exchanges.btcturk.testnet.dummy import BtcturkDummy
from src.monitoring import logger

from .testnet import BtcturkApiClientTestnet


async def test_submit_limit_order():
    client = BtcturkApiClientTestnet()
    res = await client.submit_limit_order(
        pair=create_asset_pair("BTC", "USD"),
        order_type="buy",
        price=0.000001,
        quantity=100,
    )

    print(res)
    assert res["success"] is False

    client.dummy_exchange.add_balance(Asset(symbol="TRY"), Decimal("2000"))

    res = await client.submit_limit_order(
        pair=AssetPair(base=Asset(symbol="USDT"), quote=Asset(symbol="TRY")),
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
