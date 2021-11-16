import asyncio
from decimal import Decimal

import blackops.domain.symbols as symbols
from blackops.domain.models import Asset, AssetPair
from blackops.strategies import SlidingWindow


def create_strategy(base_symbol, quote_symbol, bridge_symbol=None):
    pair = AssetPair(Asset(base_symbol), Asset(quote_symbol, Decimal(2000)))
    
    bridge_asset = None 
    if bridge_symbol:
        bridge_asset = Asset(bridge_symbol)

    stg = SlidingWindow(pair=pair, bridge=bridge_asset)
    return stg 

async def test_multiple():
    test_pairs = [
        (symbols.MANA, symbols.TRY),
        (symbols.DOGE, symbols.TRY),
        (symbols.CHZ, symbols.TRY),
        (symbols.SHIB, symbols.TRY, symbols.USDT),
        (symbols.LRC, symbols.TRY, symbols.USDT),
        (symbols.UMA, symbols.TRY, symbols.USDT),
    ]

    stgs = [create_strategy(*pair) for pair in test_pairs]
    aws = [stg.run() for stg in stgs]
    await asyncio.gather(*aws)


if __name__ == "__main__":
    asyncio.run(test_multiple())



