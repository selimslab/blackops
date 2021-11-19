import asyncio

from blackops.api.models.stg import Strategy
from blackops.trader.factory import create_trader_from_strategy

from .main import app


@app.task
def greet(name: str) -> str:
    return "hello " + name


@app.task
def run_stg(stg: Strategy):
    trader = create_trader_from_strategy(stg)
    if trader:
        asyncio.run(trader.run())
