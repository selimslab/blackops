import asyncio
from enum import Enum

from async_timeout import timeout

import blackops.pubsub.pub as pub
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
            await self.clean_task(sha)
            msg = f"Stopped tash {sha} due to timeout {timeout_seconds} seconds"
            pub.publish_message(channel=stg.sha, message=msg)
            return self.task_state[sha]
        except Exception as e:
            self.task_state[sha] = TaskStatus.FAILED

            # log
            msg = f"start_task: {sha} failed: {e}, restarting task {sha}"
            pub.publish_error(channel=stg.sha, message=msg)
            logger.error(msg)

            # restart robot
            await self.clean_task(sha)
            # TODO this will break timeout, fix it
            await self.start_task(stg, timeout_seconds)

    async def close_trader(self, sha):
        try:
            trader = self.traders.get(sha)
            if trader:
                await trader.close()
        except Exception as e:
            logger.error(f"close_trader: {e}")
            raise e

    async def clean_task(self, sha):
        try:
            await self.close_trader(sha)
            del self.traders[sha]

            self.tasks[sha].cancel()
            del self.tasks[sha]
        except Exception as e:
            logger.error(f"clean_task: {e}")
            raise e

    async def cancel_task(self, sha):
        if sha not in self.tasks:
            return
        await self.clean_task(sha)
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
