import asyncio
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import simplejson  # type: ignore

import src.pubsub.log_pub as log_pub
from src.environment import sleep_seconds
from src.monitoring import logger
from src.periodic import periodic
from src.pubsub.pubs import PublisherBase
from src.pubsub.radio import radio
from src.robots import robot_factory
from src.robots.factory import Robot  # type: ignore
from src.robots.sliding.main import SlidingWindowTrader
from src.stgs import StrategyConfig


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FlowRun:
    sha: str
    log_channel: str
    status: TaskStatus
    robot: SlidingWindowTrader
    aiotask: Optional[asyncio.Task] = None


@dataclass
class FlowRunner:
    flowruns: Dict[str, FlowRun] = field(default_factory=dict)

    def is_running(self, sha: str) -> bool:
        return sha in self.flowruns and self.flowruns[sha].status == TaskStatus.RUNNING

    @asynccontextmanager
    async def robot_context(self, flowrun: FlowRun):
        try:
            if not flowrun.aiotask:
                flowrun.aiotask = asyncio.create_task(flowrun.robot.run())
            self.flowruns[flowrun.sha] = flowrun
            flowrun.status = TaskStatus.RUNNING
            yield flowrun.aiotask
        finally:
            await self.clean_task(flowrun.sha)

    async def run_until_cancelled(self, flowrun: FlowRun):
        while True:
            async with self.robot_context(flowrun) as robot_task:
                try:
                    await robot_task
                except asyncio.CancelledError as e:
                    msg = f"{flowrun.sha} cancelled: {e}"
                    log_pub.publish_message(message=msg)
                    break
                except Exception as e:
                    flowrun.status = TaskStatus.FAILED
                    msg = f"start_robot: {flowrun.sha} failed: {e}, restarting.. {traceback.format_exc()}"
                    log_pub.publish_error(message=msg)
                    logger.error(msg)
                    continue

    async def start_flow(self, stg: StrategyConfig):
        robot = robot_factory.create_robot(stg)
        coros = [
            self.start_balance_station(robot),
            self.start_leader_station(robot),
            self.start_follower_station(robot),
            self.start_bridge_station(robot),
            self.start_robot(robot),
            self.start_stats_station(),
        ]
        coros = [c for c in coros if c]

        await asyncio.gather(*coros)

    def start_robot(self, robot: Robot):
        flowrun = FlowRun(
            sha=robot.config.sha,
            log_channel=robot.config.sha,
            robot=robot,
            status=TaskStatus.PENDING,
            aiotask=None,
        )
        return self.run_until_cancelled(flowrun)

    async def clean_task(self, sha: str) -> None:
        try:
            flowrun = self.flowruns.get(sha)
            if not flowrun:
                msg = f"clean_task: {sha} already clean"
                logger.info(msg)
                log_pub.publish_message(msg)
                return None

            if flowrun.robot:
                await flowrun.robot.close()
                self.drop_listeners(flowrun)
            if flowrun.aiotask:
                flowrun.aiotask.cancel()
                flowrun.aiotask = None

            del self.flowruns[sha]

        except Exception as e:
            msg = f"clean_task: {e}"
            logger.error(msg)
            log_pub.publish_error(msg)
            raise e

    def drop_listeners(self, flowrun: FlowRun) -> None:
        if flowrun.robot:
            # leader and follower pubs are not really publishing for now
            radio.drop_listener(log_pub.DEFAULT_CHANNEL)
            radio.drop_listener(flowrun.robot.balance_pub.pubsub_key)
            radio.drop_listener(flowrun.robot.leader_pub.pubsub_key)
            radio.drop_listener(flowrun.robot.follower_pub.pubsub_key)
            if flowrun.robot.bridge_pub:
                radio.drop_listener(flowrun.robot.bridge_pub.pubsub_key)

    def get_tasks(self) -> list:
        return list(self.flowruns.keys())

    def start_balance_station(self, robot: SlidingWindowTrader):
        return radio.create_station_if_not_exists(robot.balance_pub)

    def start_leader_station(self, robot: SlidingWindowTrader):
        return radio.create_station_if_not_exists(robot.leader_pub)

    def start_follower_station(self, robot: SlidingWindowTrader):
        return radio.create_station_if_not_exists(robot.follower_pub)

    def start_stats_station(self):
        return radio.create_station_if_not_exists(stats_pub)

    def start_bridge_station(self, robot: SlidingWindowTrader):
        if robot.bridge_pub:
            return radio.create_station_if_not_exists(robot.bridge_pub)


flow_runner = FlowRunner()


@dataclass
class StatsPub(PublisherBase):
    async def broadcast_stats(self):
        stats: Dict[str, Any] = {}

        stats["time"] = datetime.now()
        stats["radio listeners"] = {
            key: st.listeners for key, st in radio.stations.items()
        }
        for flowrun in flow_runner.flowruns.values():

            stat_dict = flowrun.robot.create_stats_message()

            stats[flowrun.sha] = stat_dict

        stats_msg = simplejson.dumps(stats, default=str)
        log_pub.publish_stats(message=stats_msg)

    async def run(self):

        await periodic(self.broadcast_stats, sleep_seconds.broadcast_stats)


stats_pub = StatsPub(pubsub_key=log_pub.DEFAULT_CHANNEL)
