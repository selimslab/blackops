import asyncio
import datetime as dt
from contextlib import asynccontextmanager

from blackops.environment import apiKey, apiSecret
from blackops.exchanges.btcturk.real import BtcturkApiClient


@asynccontextmanager
async def create_api_client():
    api_client = BtcturkApiClient(api_key=apiKey, api_secret=apiSecret)
    yield api_client
    await api_client.close_session()


async def test_get_open_orders(api_client, symbol: str = "USDTTRY"):
    res = await api_client.get_open_orders(symbol)
    print(res)


async def test_get_all_orders(api_client):

    last_hour_timestamp = dt.datetime.timestamp(
        dt.datetime.today() - dt.timedelta(hours=10)
    )
    start_date = int(last_hour_timestamp * 1000)

    params = {"pairSymbol": "USDTTRY", "limit": 20, "startDate": start_date}

    res = await api_client.get_all_orders(params)
    print(res)

    # print(real_api.get_account_balance())

    # await real_api.cancel_order(5908335899)


async def test_get_orders_after_an_id(api_client, order_id: int):

    params = {"pairSymbol": "USDTTRY", "limit": 20, "orderId": order_id}

    res = await api_client.get_all_orders(params)
    print(res)


async def test_cancel_order(api_client, order_id):
    res = await api_client.cancel_order(order_id)
    print(res)


async def test_submit_limit_order(api_client):

    res = await api_client.submit_limit_order(
        quantity=10,
        price=11,
        order_type="buy",
        pair_symbol="USDTTRY",
    )
    print(res)


async def test_bt_api():
    async with create_api_client() as api_client:
        # await test_submit_limit_order(api_client)
        # await test_get_open_orders(api_client)
        # await test_get_all_orders(api_client)
        # await test_cancel_order(api_client, order_id=5908335899)
        await test_get_orders_after_an_id(api_client, order_id=5908335899)


if __name__ == "__main__":
    asyncio.run(test_bt_api())
