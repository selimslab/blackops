import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from async_timeout import timeout

import blackops.pubsub.pub as pub
from blackops.robots.base import RobotBase
from blackops.robots.config import StrategyConfig
from blackops.robots.factory import create_trader_from_strategy
from blackops.util.logger import logger


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class Task:
    sha: str
    status: TaskStatus
    timeout: int = 0
    robot: Optional[RobotBase] = None
    aiotask: Optional[asyncio.Task] = None


class TaskContext:
    def __init__(self) -> None:
        self.tasks: Dict[str, Task] = {}

    async def start_task(
        self, stg: StrategyConfig, timeout_seconds: int = 3600
    ) -> None:
        sha = stg.sha
        if sha in self.tasks and self.tasks[sha].status == TaskStatus.RUNNING:
            raise Exception(f"{sha} already running")

        task = Task(
            sha=sha,
            timeout=timeout_seconds,
            robot=None,
            status=TaskStatus.PENDING,
            aiotask=None,
        )
        self.tasks[sha] = task

        trader = create_trader_from_strategy(stg)
        task.robot = trader

        aio_task = asyncio.create_task(trader.run())
        task.aiotask = aio_task

        try:
            async with timeout(timeout_seconds):
                task.status = TaskStatus.RUNNING
                await task.aiotask
        except TimeoutError:
            task.status = TaskStatus.COMPLETED
            await self.clean_task(sha)
            msg = f"Stopped tash {sha} due to timeout {timeout_seconds} seconds"
            pub.publish_message(channel=sha, message=msg)

        except Exception as e:
            task.status = TaskStatus.FAILED

            # log
            msg = f"start_task: {sha} failed: {e}, restarting.."
            pub.publish_error(channel=stg.sha, message=msg)
            logger.error(msg)

            # restart robot
            await self.clean_task(sha)

            # TODO this will break timeout, fix it
            await self.start_task(stg, timeout_seconds)

    async def clean_task(self, sha: str) -> None:
        try:
            task = self.tasks.get(sha)
            if not task:
                logger.error(f"clean_task: {sha} not found")
                return

            if task.robot:
                await task.robot.close()

            if task.aiotask:
                task.aiotask.cancel()

            del self.tasks[sha]
        except Exception as e:
            logger.error(f"clean_task: {e}")
            raise e

    async def cancel_task(self, sha: str) -> None:
        if sha not in self.tasks:
            logger.error(f"cancel_task: {sha} not found")
            return
        await self.clean_task(sha)
        self.tasks[sha].status = TaskStatus.STOPPED

    async def cancel_all(self) -> list:
        stopped_shas = []
        for sha, task in self.tasks.items():
            if task.status == TaskStatus.RUNNING:
                await self.cancel_task(sha)
                stopped_shas.append(sha)

        self.tasks.clear()
        return stopped_shas

    def get_orders(self, sha: str) -> list:
        task = self.tasks.get(sha)
        if task and task.robot:
            return task.robot.get_orders()
        return []

    def get_tasks(self) -> list:
        return list(self.tasks.keys())


task_context = TaskContext()
