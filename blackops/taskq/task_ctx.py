import asyncio
from enum import Enum

from async_timeout import timeout

from blackops.robots.config import StrategyConfig
from blackops.robots.factory import create_trader_from_strategy
from blackops.util.logger import logger


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class TaskContext:
    def __init__(self):
        self.tasks = {}
        self.traders = {}
        self.task_state = {}

    async def start_task(self, stg: StrategyConfig, timeout_seconds: int = 3600):
        sha = stg.sha
        if self.task_state.get(sha, "") == TaskStatus.RUNNING:
            raise Exception(f"{sha} already running")

        self.task_state[sha] = TaskStatus.PENDING
        trader = create_trader_from_strategy(stg)
        task = asyncio.create_task(trader.run())

        self.tasks[sha] = task
        self.traders[sha] = trader

        try:
            async with timeout(timeout_seconds):
                self.task_state[sha] = TaskStatus.RUNNING
                await task
        except TimeoutError:
            self.task_state[sha] = TaskStatus.COMPLETED
        except Exception as e:
            logger.error(f"start_task: {sha} failed: {e}")
            self.task_state[sha] = TaskStatus.FAILED
        finally:
            self._clean_task(sha)
            return self.task_state[sha]

    def close_trader(self, sha):
        trader = self.traders.get(sha)
        if trader:
            trader.close()

    def _clean_task(self, sha):
        self.close_trader(sha)
        del self.tasks[sha]
        del self.traders[sha]

    async def cancel_task(self, sha):
        if sha not in self.tasks:
            return
        self.tasks[sha].cancel()
        self._clean_task(sha)
        self.task_state[sha] = TaskStatus.STOPPED

    async def cancel_all(self):
        stopped_shas = []
        for sha in self.task_state:
            if self.task_state.get(sha) == TaskStatus.RUNNING:
                await self.cancel_task(sha)
                stopped_shas.append(sha)

        self.tasks.clear()
        return stopped_shas

    def get_orders(self, sha):
        trader = self.traders.get(sha)
        if trader:
            return trader.get_orders()

    def get_tasks(self):
        return list(self.tasks.keys())


task_context = TaskContext()
