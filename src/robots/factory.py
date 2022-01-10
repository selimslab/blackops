import asyncio
from dataclasses import dataclass, field
from typing import Coroutine, List, Optional

from src.monitoring import logger
from src.periodic import periodic
from src.robots.pubs import BalancePub, BookPub, StatsPub, stats_pub
from src.robots.radio import Radio, radio
from src.robots.sliding.factory import sliding_window_factory
from src.robots.sliding.main import SlidingWindowTrader
from src.stgs import StrategyConfig, StrategyType

from .runner import RobotRun, RobotRunStatus, robot_runner

Robot = SlidingWindowTrader  # union type


@dataclass
class RobotFactory:

    FACTORIES = {
        StrategyType.SLIDING_WINDOW: sliding_window_factory,
    }

    def create_robot(
        self,
        stg: StrategyConfig,
    ) -> Robot:
        try:
            stg.is_valid()
            factory_func = self.FACTORIES[StrategyType(stg.type)]
            return factory_func(stg)
        except Exception as e:
            logger.error(f"create_trader_from_strategy: {e}")
            raise e

    def get_balance_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = periodic(
            robot.balance_station.watch_balance,
            robot.config.sleep_seconds.update_balances,
        )
        return radio.create_station_if_not_exists(robot.balance_station, task_coro)

    def get_stats_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = periodic(
            robot_runner.broadcast_stats, robot.config.sleep_seconds.broadcast_stats
        )
        return radio.create_station_if_not_exists(stats_pub, task_coro)

    def get_bridge_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        if robot.bridge_station:
            task_coro = robot.bridge_station.watch_books()
            return radio.create_station_if_not_exists(robot.bridge_station, task_coro)
        return None

    def create_robot_coro(self, sha: str, robot: SlidingWindowTrader) -> Coroutine:
        robotrun = RobotRun(
            sha=sha,
            log_channel=sha,
            robot=robot,
            status=RobotRunStatus.PENDING,
            aiotask=None,
        )
        robotrun.aiotask = asyncio.create_task(robot.run())
        return robot_runner.run_forever(robotrun)

    def create_coros(self, robot: Robot) -> List[Coroutine]:
        if not robot:
            raise Exception(f"create_coros: no robot")

        if robot_runner.is_running(robot.config.sha):
            raise Exception(f"create_coros: {robot.config.sha} already running")

        coros = []

        trader_coro = self.create_robot_coro(robot.config.sha, robot)
        coros.append(trader_coro)

        balance_coro = self.get_balance_coro(robot)
        if balance_coro:
            balance_coro = self.get_balance_coro(robot)

        bridge_coro = self.get_bridge_coro(robot)
        if bridge_coro:
            coros.append(bridge_coro)

        stats_coro = self.get_stats_coro(robot)
        if stats_coro:
            coros.append(stats_coro)

        return coros


robot_factory = RobotFactory()
