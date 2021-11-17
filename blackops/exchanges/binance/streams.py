from binance import AsyncClient, BinanceSocketManager

from blackops.util.ws import reconnecting_generator


async def binance_stream_generator(symbol: str, stream_type: str):
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)
    # ts = bm.kline_socket(symbol, interval)
    # ts = bm.symbol_ticker_socket(symbol)
    ts = bm.multiplex_socket([f"{symbol.lower()}{stream_type}"])

    # then start receiving messages
    async with ts as tscm:
        while True:
            res = await tscm.recv()
            yield res


def create_book_stream(symbol: str, stream_type: str):
    return binance_stream_generator(symbol, stream_type)


if __name__ == "__main__":
    ...
