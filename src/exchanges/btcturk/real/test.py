import asyncio
import datetime as dt
import pprint
from contextlib import asynccontextmanager

from src.domain import Asset, AssetPair, create_asset_pair
from src.domain.models import OrderType
from src.environment import apiKey, apiSecret
from src.exchanges.btcturk.real.main import BtcturkApiClient
from src.numberops import round_decimal_half_up


@asynccontextmanager
async def create_api_client():
    api_client = BtcturkApiClient(api_key=apiKey, api_secret=apiSecret)
    yield api_client
    await api_client._close_session()


async def test_get_open_orders(api_client, pair: AssetPair):
    res = await api_client.get_open_orders(pair)
    pprint.pprint(res)


async def test_get_all_orders(api_client, symbol):

    last_hour_timestamp = dt.datetime.timestamp(
        dt.datetime.today() - dt.timedelta(hours=10)
    )
    start_date = int(last_hour_timestamp * 1000)

    # "startDate": start_date

    params = {"pairSymbol": symbol, "limit": 20}

    res = await api_client.get_all_orders(params)
    pprint.pprint(res)

    # print(real_api.get_account_balance())

    # await real_api.cancel_order(5908335899)


async def test_get_orders_after_an_id(api_client, order_id: int):

    params = {"pairSymbol": "USDTTRY", "limit": 20, "orderId": order_id}

    res = await api_client.get_all_orders(params)
    pprint.pprint(res)


async def test_cancel_order(api_client, order_id: int):
    res = await api_client.cancel_order(order_id)
    pprint.pprint(res)


async def test_cancel_open_orders(api_client, symbol):
    res = await api_client.cancel_open_orders(symbol)
    pprint.pprint(res)


async def test_submit_limit_order(api_client):

    res = await api_client.submit_limit_order(
        quantity=3.32,
        price=571.65,
        side=OrderType.SELL,
        pair=create_asset_pair("AVAX", "TRY"),
    )
    pprint.pprint(res)

    data = res.get("data", {})
    if data:
        order_id = data.get("id")

        print("order_id:", order_id)


async def test_get_account_balance(api_client):
    res = await api_client.get_account_balance()  # symbols=["XRP", "USDT"]
    pprint.pprint(res)


async def test_bt_api():
    async with create_api_client() as api_client:
        await test_submit_limit_order(api_client)

        # await test_get_all_orders(api_client, "XRPUSDT")

        # # await test_get_orders_after_an_id(api_client, order_id=5980501563)

        # await test_cancel_order(api_client, order_id=5353)
        # await test_get_open_orders(api_client, create_asset_pair("FTM", "TRY"))

        # await test_cancel_open_orders(api_client, "USDTTRY")

        # # await test_get_account_balance(api_client)

        # await test_get_account_balance(api_client)

        # res = api_client.get_ticker(
        #     pair=create_asset_pair("ETH", "USDT"),
        # )
        # print(res)


async def test_rate_limit():
    async with create_api_client() as api_client:
        pass


if __name__ == "__main__":
    asyncio.run(test_bt_api())
