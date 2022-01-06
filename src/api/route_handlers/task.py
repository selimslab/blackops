import asyncio

import src.pubsub.pub as pub
from src.robots.config import STRATEGY_CLASS, StrategyConfig, StrategyType
from src.robots.context import robot_context
from src.monitoring import logger

from .stg import get_stg


async def deserialize_stg_config(sha: str) -> StrategyConfig:
    stg_dict: dict = await get_stg(sha)

    stg_type = StrategyType(stg_dict.get("type"))

    STG_CLASS = STRATEGY_CLASS[stg_type]

    stg: StrategyConfig = STG_CLASS(**stg_dict)

    return stg


def run_task(stg: StrategyConfig):
    # run as long as the task is not cancelled
    asyncio.run(robot_context.start_task(stg))


async def stop_task(sha: str):
    await robot_context.cancel_task(sha)
    pub.publish_message(sha, f"{sha} stopped")


async def stop_all_tasks():
    return await robot_context.cancel_all()


def get_tasks():
    return robot_context.get_tasks()
