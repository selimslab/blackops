import asyncio

from blackops.trader.factory import create_trader_from_strategy


class TaskContext:
    def __init__(self):
        self.tasks = {}

    async def start_task(self, stg: dict):
        sha = stg.get("sha")
        if sha in self.tasks:
            raise Exception("Task already running")
        trader = await create_trader_from_strategy(stg)
        task = asyncio.create_task(trader.run())
        self.tasks[sha] = task
        await task

    async def cancel_task(self, sha):
        if sha in self.tasks:
            self.tasks[sha].cancel()
            del self.tasks[sha]
        else:
            raise Exception("Task not found")

    async def cancel_all(self):
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()


context = TaskContext()
