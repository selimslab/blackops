import asyncio

from blackops.trader.factory import create_trader_from_strategy


class TaskContext:
    def __init__(self):
        self.tasks = {}
        self.traders = {}
        self.task_state = {}

    async def start_task(self, stg: dict):
        sha = stg.get("sha")
        if sha in self.tasks:
            raise Exception("Task already running")
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
        else:
            raise Exception("Task not found")

    async def cancel_all(self):
        for sha, task in self.tasks.items():
            task.cancel()
            self.task_state[sha] = "STOPPED"
        # self.tasks.clear()

    def get_orders(self, sha):
        trader = self.traders.get(sha)
        if trader:
            return trader.get_orders()


context = TaskContext()
