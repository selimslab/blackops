import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Coroutine, Dict, Optional, List

import src.pubsub.pub as pub
from src.robots.base import RobotBase
from src.stgs import StrategyConfig
from src.robots.factory import create_trader_from_strategy
from src.robots.sliding.main import SlidingWindowTrader
from src.robots.watchers import BalanceWatcher, BookWatcher
from src.monitoring import logger
from src.periodic import periodic

from src.robots.radio import radio, Radio, Station


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
class BalancePublisher:
    radio: Radio = radio


    def get_balance_task(
        self, config: StrategyConfig, balance_watcher: BalanceWatcher
    ) -> Optional[Coroutine]:
        if balance_watcher.pubsub_key in self.radio.stations:
            self.radio.add_listener(balance_watcher.pubsub_key)
            return None
        else:
            station = Station(
                pubsub_channel=balance_watcher.pubsub_key,
                log_channel=config.sha,
                listeners=1,
            )
            balance_task = periodic(
                balance_watcher.watch_balance, config.sleep_seconds.update_balances
            )
            station.aiotask = asyncio.create_task(balance_task)
            self.radio.stations[station.pubsub_channel] = station
            return self.radio.start_station(station)


@dataclass
class BridgePublisher:
    radio: Radio = radio

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

bridge_publisher = BridgePublisher()
balance_publisher = BalancePublisher()


@dataclass
class RobotContext:
    robots: Dict[str, RobotRun] = field(default_factory=dict)
    balance_publisher = balance_publisher
    bridge_publisher = bridge_publisher
    

    async def start_robot(self, robotrun: RobotRun):
        if not robotrun.aiotask:
            raise Exception(f"no aiotask for robotrun")
        try:
            self.robots[robotrun.sha] = robotrun
            robotrun.status = RobotRunStatus.RUNNING
            await robotrun.aiotask
        except asyncio.CancelledError as e:
            msg = f"{robotrun.sha} cancelled: {e}"
            pub.publish_error(channel=robotrun.log_channel, message=msg)
            await self.clean_task(robotrun.sha)
        except Exception as e:
            robotrun.status = RobotRunStatus.FAILED
            # log
            msg = f"start_robot: {robotrun.sha} failed: {e}, restarting.."
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
        return self.start_robot(robotrun)


    async def create_coros(self, stg: StrategyConfig) -> List[Coroutine]:
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

        balance_task = self.balance_publisher.get_balance_task(stg, balance_watcher)
        if balance_task:
            coros.append(balance_task)

        if bridge_watcher:
            bridge_task = self.bridge_publisher.get_bridge_task(stg, bridge_watcher)
            if bridge_task:
                coros.append(bridge_task)

        print("robots", self.robots.keys())
        print("stations", radio.stations.keys())

        return coros 


    async def clean_task(self, sha: str) -> None:
        try:
            robotrun = self.robots.get(sha)
            if not robotrun:
                logger.error(f"clean_task: {sha} not found")
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

    def drop_listeners(self,robotrun: RobotRun) -> None:
        if robotrun.robot:
            radio.drop_listener(robotrun.robot.balance_pubsub_key)
            if robotrun.robot.bridge_pubsub_key:
                radio.drop_listener(robotrun.robot.bridge_pubsub_key)


    async def cancel_task(self, sha: str) -> None:
        if sha not in self.robots:
            logger.error(f"cancel_task: {sha} not found")
            return
        await self.clean_task(sha)
        print("robots", self.robots.keys())
        print("stations", radio.stations.keys())

    async def cancel_all(self) -> list:
        stopped_shas = []
        for sha, task in self.robots.items():
            if task.status == RobotRunStatus.RUNNING:
                await self.cancel_task(sha)
                stopped_shas.append(sha)

        self.robots.clear()
        return stopped_shas

    def get_tasks(self) -> list:
        return list(self.robots.keys())


robot_context = RobotContext()
