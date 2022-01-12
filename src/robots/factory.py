from dataclasses import dataclass
from typing import Coroutine, List, Optional

import src.pubsub.log_pub as log_pub
from src.environment import SleepSeconds
from src.monitoring import logger
from src.periodic import periodic
from src.pubsub.pubs import BalancePub, BookPub, StatsPub, stats_pub
from src.pubsub.radio import Radio, radio
from src.robots.sliding.factory import sliding_window_factory
from src.robots.sliding.main import SlidingWindowTrader
from src.stgs import StrategyConfig, StrategyType

from .runner import RobotRun, TaskStatus, robot_runner

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
            msg = f"create_trader_from_strategy: {e}"
            logger.error(msg)
            log_pub.publish_error(msg)
            raise e

    def get_balance_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = periodic(
            robot.balance_pub.ask_balance,
            SleepSeconds.update_balances,
        )
        return radio.create_station_if_not_exists(robot.balance_pub, task_coro)

    def get_leader_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = robot.leader_pub.consume_stream()
        return radio.create_station_if_not_exists(robot.leader_pub, task_coro)

    def get_follower_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = robot.follower_pub.consume_stream()
        return radio.create_station_if_not_exists(robot.follower_pub, task_coro)

    def get_stats_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        task_coro = periodic(robot_runner.broadcast_stats, SleepSeconds.broadcast_stats)
        return radio.create_station_if_not_exists(stats_pub, task_coro)

    def get_bridge_coro(self, robot: SlidingWindowTrader) -> Optional[Coroutine]:
        if robot.bridge_pub:
            task_coro = robot.bridge_pub.consume_stream()
            return radio.create_station_if_not_exists(robot.bridge_pub, task_coro)
        return None

    def get_robot_coro(self, sha: str, robot: SlidingWindowTrader) -> Coroutine:
        robotrun = RobotRun(
            sha=sha,
            log_channel=sha,
            robot=robot,
            status=TaskStatus.PENDING,
            aiotask=None,
        )
        return robot_runner.run_until_cancelled(robotrun)

    def create_coros(self, robot: Robot) -> List[Coroutine]:
        if not robot:
            raise Exception(f"create_coros: no robot")

        if robot_runner.is_running(robot.config.sha):
            raise Exception(f"create_coros: {robot.config.sha} already running")

        coros = []

        trader_coro = self.get_robot_coro(robot.config.sha, robot)
        coros.append(trader_coro)

        leader_pub_coro = self.get_leader_coro(robot)
        if leader_pub_coro:
            coros.append(leader_pub_coro)

        follower_pub_coro = self.get_follower_coro(robot)
        if follower_pub_coro:
            coros.append(follower_pub_coro)

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
