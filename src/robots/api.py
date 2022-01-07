import asyncio
from dataclasses import dataclass
import src.pubsub.pub as pub
from src.robots.context import robot_context
from src.monitoring import logger
from src.stgs import StrategyConfig

@dataclass
class RobotApi:

    def run_task(self, stg: StrategyConfig):
        # run as long as the task is not cancelled
        asyncio.run(robot_context.start_task(stg))


    async def stop_task(self, sha: str):
        await robot_context.cancel_task(sha)
        pub.publish_message(sha, f"{sha} stopped")


    async def stop_all_tasks(self):
        return await robot_context.cancel_all()

    def get_tasks(self):
        return robot_context.get_tasks()


robot_api = RobotApi()