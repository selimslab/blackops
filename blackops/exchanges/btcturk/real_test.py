import asyncio
import datetime as dt
import pprint
from contextlib import asynccontextmanager
from dataclasses import dataclass

import async_timeout
from dotenv.main import resolve_variables

from blackops.domain.asset import Asset, AssetPair
from blackops.environment import apiKey, apiSecret
from blackops.exchanges.btcturk.real import BtcturkApiClient


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
        quantity=10,
        price=1,
        order_type="sell",
        pair=AssetPair(Asset(symbol="XRP"), Asset(symbol="USDT")),
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
        # await test_submit_limit_order(api_client)

        # await test_get_all_orders(api_client, "XRPUSDT")

        # # await test_get_orders_after_an_id(api_client, order_id=5980501563)

        # await test_cancel_order(api_client, order_id=5353)
        # await test_get_open_orders(
        #     api_client, AssetPair(Asset(symbol="XRP"), Asset(symbol="USDT"))
        # )

        # await test_cancel_open_orders(api_client, "USDTTRY")

        # # await test_get_account_balance(api_client)

        # await test_get_account_balance(api_client)

        # res = api_client.get_ticker(
        #     pair=AssetPair(Asset(symbol="ETH"), Asset(symbol="USDT"))
        # )
        # print(res)
        pass


async def test_rate_limit():
    async with create_api_client() as api_client:
        pass


@dataclass
class Test:
    order_lock = asyncio.Lock()

    @asynccontextmanager
    async def timed_order_context(self):
        async with self.order_lock:
            yield
            await asyncio.sleep(0.1)
        # try:
        #     lock = self.order_lock.acquire(timeout=0.1)
        #     if lock:
        #          yield
        # finally:
        #     self.order_lock.release()

        # try:
        #     yield
        #     self.order_in_progress = True
        #     await asyncio.sleep(0.5)
        # finally:
        #     self.order_in_progress = False

    async def order(self, i):
        if self.order_lock.locked():
            return f"order_in_progress", i
        async with self.timed_order_context():
            return i


async def robot(name, t):
    for i in range(10):
        res = await t.order(f"{name} {i}")
        print(res)
        await asyncio.sleep(0.03)


async def test_order_lock():
    t = Test()

    # async def robot2():
    #     for i in range(10):
    #         await t.order()
    #         # await asyncio.sleep(0.05)

    aws = asyncio.gather(robot("x", t), robot("y", t))
    await aws


if __name__ == "__main__":
    # asyncio.run(test_bt_api())
    asyncio.run(test_order_lock())
