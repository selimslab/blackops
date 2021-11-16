import asyncio

from binance import AsyncClient, BinanceSocketManager


async def ws_generator_binance(symbol: str):
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)
    # start any sockets here, i.e a trade socket
    # ts = bm.kline_socket(symbol, interval)
    # ts = bm.symbol_ticker_socket(symbol)
    ts = bm.multiplex_socket([f"{symbol.lower()}@bookTicker"])

    # then start receiving messages
    async with ts as tscm:
        while True:
            res = await tscm.recv()
            yield res

    # await client.close_connection()


# def start_binance_stream(symbol:str, interval:str='1m'):
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(main(symbol, interval))


def currency_bridge(target: str, bridge: str):
    ...
