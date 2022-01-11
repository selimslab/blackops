import asyncio
from dataclasses import dataclass
from typing import List

import src.pubsub.log_pub as log_pub
from src.monitoring import logger
from src.periodic import periodic
from src.robots.factory import robot_factory
from src.robots.runner import robot_runner
from src.stgs import StrategyConfig


@dataclass
class RobotApi:
    @staticmethod
    async def run_task(stg: StrategyConfig):
        if robot_runner.is_running(stg.sha):
            raise Exception(f"{stg.sha} already running")

        robot = robot_factory.create_robot(stg)
        coros = robot_factory.create_coros(robot)
        try:
            # coros are self-healing so if we have an error here, it means a problem
            await asyncio.gather(*coros)
        except Exception as e:
            msg = f"{stg.sha} failed: {e}, along with the radios"
            logger.error(msg)
            log_pub.publish_message(message=msg)

    async def stop_task(self, sha: str):
        await robot_runner.cancel_task(sha)
        msg = f"{sha} stopped"
        logger.info(msg)
        log_pub.publish_message(message=msg)
        return sha

    async def stop_all_tasks(self) -> List[str]:
        stopped = await robot_runner.cancel_all()
        msg = f"{stopped} stopped"
        logger.info(msg)
        log_pub.publish_message(message=msg)
        return stopped

    def get_tasks(self) -> List[str]:
        return robot_runner.get_tasks()


robot_api = RobotApi()
