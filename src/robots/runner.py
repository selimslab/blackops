import asyncio
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

import simplejson as json  # type: ignore

import src.pubsub.pub as pub
from src.monitoring import logger
from src.robots.radio import Radio, radio
from src.robots.sliding.main import SlidingWindowTrader


class RobotRunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RobotRun:
    sha: str
    log_channel: str
    status: RobotRunStatus
    robot: SlidingWindowTrader
    aiotask: Optional[asyncio.Task] = None


@dataclass
class RobotRunner:
    robots: Dict[str, RobotRun] = field(default_factory=dict)

    def is_running(self, sha: str) -> bool:
        return sha in self.robots and self.robots[sha].status == RobotRunStatus.RUNNING

    @asynccontextmanager
    async def robot_context(self, robotrun: RobotRun):
        try:
            if not robotrun.aiotask:
                raise Exception(f"no aiotask for robotrun")
            self.robots[robotrun.sha] = robotrun
            robotrun.status = RobotRunStatus.RUNNING
            yield robotrun.aiotask
        finally:
            await self.clean_task(robotrun.sha)

    async def run_forever(self, robotrun: RobotRun):
        while True:
            async with self.robot_context(robotrun) as robot_task:
                try:
                    await robot_task
                except asyncio.CancelledError as e:
                    msg = f"{robotrun.sha} cancelled: {e}"
                    pub.publish_error(message=msg)
                    raise
                except Exception as e:
                    robotrun.status = RobotRunStatus.FAILED
                    msg = f"start_robot: {robotrun.sha} failed: {e}, restarting.. {traceback.format_exc()}"
                    pub.publish_error(message=msg)
                    logger.error(msg)
                    continue

    async def clean_task(self, sha: str) -> None:
        try:
            robotrun = self.robots.get(sha)
            if not robotrun:
                logger.info(f"clean_task: {sha} not found")
                return

            if robotrun.aiotask:
                robotrun.aiotask.cancel()

            if robotrun.robot:
                await robotrun.robot.close()
                self.drop_listeners(robotrun)

            del self.robots[sha]
        except Exception as e:
            logger.error(f"clean_task: {e}")
            raise e

    def drop_listeners(self, robotrun: RobotRun) -> None:
        if robotrun.robot:
            radio.drop_listener(pub.DEFAULT_CHANNEL)
            radio.drop_listener(robotrun.robot.balance_station.pubsub_key)
            if robotrun.robot.bridge_station:
                radio.drop_listener(robotrun.robot.bridge_station.pubsub_key)

    async def cancel_task(self, sha: str) -> None:
        if sha not in self.robots:
            logger.error(f"cancel_task: {sha} not found")
            return
        await self.clean_task(sha)

    async def cancel_all(self) -> list:
        stopped_shas = []
        for sha in self.robots:
            await self.cancel_task(sha)
            stopped_shas.append(sha)

        self.robots.clear()
        return stopped_shas

    def get_tasks(self) -> list:
        return list(self.robots.keys())

    async def broadcast_stats(self) -> None:
        stats = {}
        for robotrun in self.robots.values():

            stat_dict = robotrun.robot.create_stats_message()

            stats[robotrun.sha] = stat_dict

        if stats:
            stats_msg = json.dumps(stats, default=str)
            pub.publish_stats(message=stats_msg)


robot_runner = RobotRunner()
