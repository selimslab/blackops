import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Coroutine, Dict, Optional

import blackops.pubsub.pub as pub
from blackops.robots.base import RobotBase
from blackops.robots.config import StrategyConfig
from blackops.robots.factory import create_trader_from_strategy
from blackops.robots.sliding.main import SlidingWindowTrader
from blackops.robots.watchers import BalanceWatcher, BookWatcher
from blackops.util.logger import logger
from blackops.util.periodic import periodic


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
class Station:
    pubsub_channel: str
    log_channel: str
    listeners: int = 0
    aiotask: Optional[asyncio.Task] = None


@dataclass
class Radio:
    stations: Dict[str, Station] = field(default_factory=dict)

    async def start_station(self, station: Station):
        if not station.aiotask:
            raise Exception(f"no aiotask set for station")
        try:
            await station.aiotask
        except asyncio.CancelledError as e:
            msg = f"station {station.pubsub_channel} cancelled: {e}"
            pub.publish_error(channel=station.log_channel, message=msg)
            del self.stations[station.pubsub_channel]
        except Exception as e:
            msg = f"restarting station {station.pubsub_channel}: {e}"
            pub.publish_error(channel=station.log_channel, message=msg)
            logger.error(msg)
            await self.start_station(station)

    def add_listener(self, pubsub_channel: str):
        if pubsub_channel in self.stations:
            self.stations[pubsub_channel].listeners += 1

    def drop_listener(self, pubsub_channel: str):
        station = self.stations.get(pubsub_channel)
        if station:
            self.stations[station.pubsub_channel].listeners -= 1
            self.stop_station_if_no_listeners(station)

    def stop_station_if_no_listeners(self, station: Station):
        if station.listeners == 0 and station.aiotask:
            station.aiotask.cancel()


@dataclass
class RobotContext:
    robots: Dict[str, RobotRun] = field(default_factory=dict)
    radio: Radio = field(default_factory=Radio)

    async def start_robot(self, robotrun: RobotRun):
        if not robotrun.aiotask:
            raise Exception(f"no aiotask for robotrun")
        try:
            robotrun.status = RobotRunStatus.RUNNING
            await robotrun.aiotask
        except asyncio.CancelledError as e:
            msg = f"{robotrun.sha} cancelled: {e}"
            pub.publish_error(channel=robotrun.log_channel, message=msg)
            await self.clean_task(robotrun.sha)
        except Exception as e:
            robotrun.status = RobotRunStatus.FAILED
            # log
            msg = f"start_task: {robotrun.sha} failed: {e}, restarting.."
            pub.publish_error(channel=robotrun.log_channel, message=msg)
            logger.error(msg)

            # restart robot
            await self.clean_task(robotrun.sha)
            await self.start_robot(robotrun)

    def get_robot_task(self, sha: str, robot: SlidingWindowTrader) -> Coroutine:
        robotrun = RobotRun(
            sha=sha,
            log_channel=sha,
            robot=robot,
            status=RobotRunStatus.PENDING,
            aiotask=None,
        )
        robotrun.aiotask = asyncio.create_task(robot.run())
        self.robots[sha] = robotrun
        return self.start_robot(robotrun)

    def get_balance_task(
        self, stg: StrategyConfig, balance_watcher: BalanceWatcher
    ) -> Optional[Coroutine]:
        if balance_watcher.pubsub_key in self.radio.stations:
            self.radio.add_listener(balance_watcher.pubsub_key)
            return None
        else:
            station = Station(
                pubsub_channel=balance_watcher.pubsub_key,
                log_channel=stg.sha,
                listeners=1,
            )
            balance_task = periodic(
                balance_watcher.watch_balance, stg.sleep_seconds.update_balances
            )
            station.aiotask = asyncio.create_task(balance_task)
            self.radio.stations[station.pubsub_channel] = station
            return self.radio.start_station(station)

    def get_bridge_task(
        self, stg: StrategyConfig, bridge_watcher: BookWatcher
    ) -> Optional[Coroutine]:
        if bridge_watcher.pubsub_key in self.radio.stations:
            self.radio.add_listener(bridge_watcher.pubsub_key)
            return None
        else:
            station = Station(
                pubsub_channel=bridge_watcher.pubsub_key,
                log_channel=stg.sha,
                listeners=1,
            )
            bridge_task = bridge_watcher.watch_books()
            station.aiotask = asyncio.create_task(bridge_task)
            self.radio.stations[station.pubsub_channel] = station
            return self.radio.start_station(station)

    async def start_task(self, stg: StrategyConfig) -> None:
        sha = stg.sha
        if sha in self.robots and self.robots[sha].status == RobotRunStatus.RUNNING:
            raise Exception(f"{sha} already running")

        robot, balance_watcher, bridge_watcher = create_trader_from_strategy(stg)
        if not robot:
            raise Exception(f"start_task: no robot")

        if not balance_watcher:
            raise Exception(f"start_task: no balance_watcher")

        coros = []

        robot_task = self.get_robot_task(stg.sha, robot)
        coros.append(robot_task)

        balance_task = self.get_balance_task(stg, balance_watcher)
        if balance_task:
            coros.append(balance_task)

        if bridge_watcher:
            bridge_task = self.get_bridge_task(stg, bridge_watcher)
            if bridge_task:
                coros.append(bridge_task)

        print("robots", self.robots.keys())
        print("stations", self.radio.stations.keys())

        await asyncio.gather(*coros)

    async def clean_task(self, sha: str) -> None:
        try:
            robotrun = self.robots.get(sha)
            if not robotrun:
                logger.error(f"clean_task: {sha} not found")
                return

            if robotrun.robot:
                await robotrun.robot.close()
                self.radio.drop_listener(robotrun.robot.balance_pubsub_key)
                if robotrun.robot.bridge_pubsub_key:
                    self.radio.drop_listener(robotrun.robot.bridge_pubsub_key)

            if robotrun.aiotask:
                robotrun.aiotask.cancel()

            del self.robots[sha]
        except Exception as e:
            logger.error(f"clean_task: {e}")
            raise e

    async def cancel_task(self, sha: str) -> None:
        if sha not in self.robots:
            logger.error(f"cancel_task: {sha} not found")
            return
        await self.clean_task(sha)
        print("robots", self.robots.keys())
        print("stations", self.radio.stations.keys())

    async def cancel_all(self) -> list:
        stopped_shas = []
        for sha, task in self.robots.items():
            if task.status == RobotRunStatus.RUNNING:
                await self.cancel_task(sha)
                stopped_shas.append(sha)

        self.robots.clear()
        return stopped_shas

    def get_orders(self, sha: str) -> list:
        task = self.robots.get(sha)
        if task and task.robot:
            return task.robot.get_orders()
        return []

    def get_tasks(self) -> list:
        return list(self.robots.keys())


task_context = RobotContext()
