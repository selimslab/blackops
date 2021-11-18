import asyncio
from decimal import Decimal

import blackops.domain.symbols as symbols
from blackops.trader.factory import create_trader_from_strategy
from blackops.api.models.stg import SlidingWindow, SlidingWindowWithBridge

import cProfile
from pstats import Stats


async def test_sliding_window():
    sw = SlidingWindowWithBridge(
        base='BTC',
        quote='TRY',
        bridge='USDT',
        max_usable_quote_amount_y=5000,
        step_count=20,
        step_constant_k=0.001,
        credit=0.75,
    )

    trader = create_trader_from_strategy(sw)

    await asyncio.gather(trader.run())


def profile():
    pr = cProfile.Profile()
    pr.enable()

    asyncio.run(test_sliding_window())

    pr.disable()
    stats = Stats(pr)
    stats.sort_stats('time').print_stats(10)


if __name__ == "__main__":
    asyncio.run(test_sliding_window())
