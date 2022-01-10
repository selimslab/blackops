import asyncio
from dataclasses import dataclass
from typing import List

import simplejson as json  # type: ignore

import src.pubsub.pub as pub
from src.monitoring import logger
from src.periodic import periodic
from src.robots.context import robot_context
from src.stgs import StrategyConfig


@dataclass
class RobotApi:
    def is_running(self, stg: StrategyConfig):
        if robot_context.is_running(stg.sha):
            raise Exception(f"{stg.sha} already running")

    async def run_task(self, stg: StrategyConfig):
        self.is_running(stg)
        coros = await robot_context.create_coros(stg)
        try:
            await asyncio.gather(*coros)
        except asyncio.CancelledError as e:
            logger.info(f"{stg.sha} cancelled: {e}")
            raise
        except Exception as e:
            logger.error(f"{stg.sha} failed: {e}")

    async def stop_task(self, sha: str):
        await robot_context.cancel_task(sha)
        pub.publish_message(message=f"{sha} stopped")
        return sha

    async def stop_all_tasks(self) -> List[str]:
        shas = robot_context.get_tasks()
        stopped = await robot_context.cancel_all()
        for sha in shas:
            pub.publish_message(message=f"{sha} stopped")
        return stopped

    def get_tasks(self) -> List[str]:
        return robot_context.get_tasks()


robot_api = RobotApi()
