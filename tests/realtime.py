import asyncio
from decimal import Decimal

import blackops.domain.symbols as symbols
from blackops.trader.factory import create_trader_from_strategy
from blackops.api.models.stg import SlidingWindow, SlidingWindowWithBridge

import cProfile
from pstats import Stats


async def test_sliding_window_with_bridge():
    sw = SlidingWindowWithBridge(
        base='UMA',
        quote='TRY',
        bridge='USDT',
        max_usable_quote_amount_y=10000,
        step_count=20,
        step_constant_k=0.2,
        credit=0.75,
    )


    trader = create_trader_from_strategy(dict(sw))

    print(trader)

    await asyncio.gather(trader.run())


def profile(func):
    pr = cProfile.Profile()
    pr.enable()

    func()

    pr.disable()
    stats = Stats(pr)
    stats.sort_stats('time').print_stats(10)


if __name__ == "__main__":
    asyncio.run(test_sliding_window_with_bridge())
