import asyncio

from blackops.trader.factory import create_trader_from_strategy


class TaskContext:
    def __init__(self):
        self.tasks = {}
        self.traders = {}
        self.task_state = {}

    async def start_task(self, stg: dict):
        sha = stg.get("sha")
        if self.tasks.get("sha", "") == "RUNNING":
            raise Exception(f"{sha} already running")

        trader = await create_trader_from_strategy(stg)

        task = asyncio.create_task(trader.run())

        self.tasks[sha] = task
        self.traders[sha] = trader
        self.task_state[sha] = "RUNNING"

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
        n = len(self.tasks)
        for sha in self.tasks:
            await self.cancel_task(sha)

        return n
        # self.tasks.clear()

    def get_orders(self, sha):
        trader = self.traders.get(sha)
        if trader:
            return trader.get_orders()

    def get_tasks(self):
        return self.tasks


task_context = TaskContext()
