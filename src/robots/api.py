import asyncio
from dataclasses import dataclass
from typing import List

import src.pubsub.pub as pub
from src.monitoring import logger
from src.periodic import periodic
from src.robots.factory import robot_factory
from src.robots.runner import robot_runner
from src.stgs import StrategyConfig


@dataclass
class RobotApi:
    async def run_task(self, stg: StrategyConfig):
        if robot_runner.is_running(stg.sha):
            raise Exception(f"{stg.sha} already running")

        coros = robot_factory.create_coros(stg)
        try:
            await asyncio.gather(*coros)
        except asyncio.CancelledError as e:
            logger.info(f"{stg.sha} cancelled: {e}")
            raise
        except Exception as e:
            msg = f"{stg.sha} failed: {e}"
            logger.error(msg)
            pub.publish_message(message=msg)

    async def stop_task(self, sha: str):
        await robot_runner.cancel_task(sha)
        pub.publish_message(message=f"{sha} stopped")
        return sha

    async def stop_all_tasks(self) -> List[str]:
        stopped = await robot_runner.cancel_all()
        pub.publish_message(message=f"{stopped} stopped")
        return stopped

    def get_tasks(self) -> List[str]:
        return robot_runner.get_tasks()


robot_api = RobotApi()
