import asyncio

import blackops.domain.symbols as symbols
from blackops.domain.models import Asset, AssetPair
from blackops.strategies.real import WindowBreaker


def create_strategy(base_symbol, quote_symbol, bridge_symbol=None):
    pair = AssetPair(Asset(base_symbol), Asset(quote_symbol))
    
    bridge_asset = None 
    if bridge_symbol:
        bridge_asset = Asset(bridge_symbol)

    stg = WindowBreaker(pair=pair, bridge=bridge_asset)
    return stg 

def start_real():
    stg = create_strategy(symbols.UMA, symbols.TRY, symbols.USDT)
    asyncio.run(stg.run())

if __name__ == "__main__":
    start_real()