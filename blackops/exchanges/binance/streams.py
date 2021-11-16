from binance import AsyncClient, BinanceSocketManager


async def binance_stream_generator(symbol: str, stream_id:str):
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)
    # start any sockets here, i.e a trade socket
    # ts = bm.kline_socket(symbol, interval)
    # ts = bm.symbol_ticker_socket(symbol)
    ts = bm.multiplex_socket([f"{symbol.lower()}{stream_id}"])

    # then start receiving messages
    async with ts as tscm:
        while True:
            res = await tscm.recv()
            yield res



def currency_bridge(target: str, bridge: str):
    ...

if __name__ == "__main__":
    ...