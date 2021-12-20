import asyncio
import datetime as dt
import pprint
from contextlib import asynccontextmanager

from blackops.domain.asset import Asset, AssetPair
from blackops.environment import apiKey, apiSecret
from blackops.exchanges.btcturk.real import BtcturkApiClient


@asynccontextmanager
async def create_api_client():
    api_client = BtcturkApiClient(api_key=apiKey, api_secret=apiSecret)
    yield api_client
    await api_client._close_session()


async def test_get_open_orders(api_client, symbol: str = "USDTTRY"):
    res = await api_client.get_open_orders(symbol)
    pprint.pprint(res)


async def test_get_all_orders(api_client):

    last_hour_timestamp = dt.datetime.timestamp(
        dt.datetime.today() - dt.timedelta(hours=10)
    )
    start_date = int(last_hour_timestamp * 1000)

    # "startDate": start_date

    params = {"pairSymbol": "USDTTRY", "limit": 20}

    res = await api_client.get_all_orders(params)
    pprint.pprint(res)

    # print(real_api.get_account_balance())

    # await real_api.cancel_order(5908335899)


async def test_get_orders_after_an_id(api_client, order_id: int):

    params = {"pairSymbol": "USDTTRY", "limit": 20, "orderId": order_id}

    res = await api_client.get_all_orders(params)
    pprint.pprint(res)


async def test_cancel_order(api_client, order_id):
    res = await api_client.cancel_order(order_id)
    pprint.pprint(res)


async def test_cancel_open_orders(api_client, symbol):
    res = await api_client.cancel_open_orders(symbol)
    pprint.pprint(res)


async def test_submit_limit_order(api_client):

    res = await api_client.submit_limit_order(
        quantity=10,
        price=18.42,
        order_type="sell",
        pair=AssetPair(Asset("USDT"), Asset("TRY")),
    )
    pprint.pprint(res)

    data = res.get("data")
    if data:
        order_id = data.get("id")

        print("order_id:", order_id)


async def test_get_account_balance(api_client):
    res = await api_client.get_account_balance(assets=["XRP", "USDT"])
    pprint.pprint(res)


async def test_bt_api():
    async with create_api_client() as api_client:
        await test_submit_limit_order(api_client)

        # await test_get_open_orders(api_client)

        # await test_get_all_orders(api_client)

        # await test_get_orders_after_an_id(api_client, order_id=5980501563)

        # await test_cancel_order(api_client, order_id=5908335899)

        # await test_cancel_open_orders(api_client, "USDTTRY")

        # await test_get_account_balance(api_client)

        # await test_get_account_balance(api_client)


if __name__ == "__main__":
    asyncio.run(test_bt_api())
