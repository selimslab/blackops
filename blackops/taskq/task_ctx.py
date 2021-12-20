import asyncio

from async_timeout import timeout

from blackops.robots.config import StrategyConfig
from blackops.robots.factory import create_trader_from_strategy


class TaskContext:
    def __init__(self):
        self.tasks = {}
        self.traders = {}
        self.task_state = {}

    async def start_task(self, stg: StrategyConfig, timeout_seconds: int = 3600):
        sha = stg.sha
        if self.task_state.get(sha, "") == "RUNNING":
            raise Exception(f"{sha} already running")

        trader = create_trader_from_strategy(stg)
        task = asyncio.create_task(trader.run())

        self.tasks[sha] = task
        self.traders[sha] = trader
        self.task_state[sha] = "RUNNING"

        async with timeout(timeout_seconds):
            await task

    async def cancel_task(self, sha):
        if sha in self.tasks:
            self.tasks[sha].cancel()
            del self.tasks[sha]
            del self.traders[sha]
            self.task_state[sha] = "STOPPED"
        else:
            raise Exception("Task not found")

    async def cancel_all(self):
        n = 0
        for sha in self.task_state:
            if self.task_state.get(sha) == "RUNNING":
                await self.cancel_task(sha)
                n += 1

        return n
        # self.tasks.clear()

    def get_orders(self, sha):
        trader = self.traders.get(sha)
        if trader:
            return trader.get_orders()

    def get_tasks(self):
        return list(self.tasks.keys())


task_context = TaskContext()
