import asyncio
import hashlib
from typing import List, OrderedDict

import simplejson as json
from fastapi import HTTPException

import blackops.pubsub.pub as pub
from blackops.robots.config import STRATEGY_CLASS, StrategyConfig, StrategyType
from blackops.taskq.redis import (
    LOG_CHANNELS,
    RUNNING_TASKS,
    STG_MAP,
    async_redis_client,
)
from blackops.taskq.task_ctx import task_context
from blackops.util.logger import logger

from .stg import get_stg


async def get_task_id(sha):
    return await async_redis_client.hget(RUNNING_TASKS, sha)


async def deserialize_stg_config(sha: str) -> StrategyConfig:
    stg_dict: dict = await get_stg(sha)

    stg_type = StrategyType(stg_dict.get("type"))

    STG_CLASS = STRATEGY_CLASS[stg_type]

    stg: StrategyConfig = STG_CLASS(**stg_dict)

    return stg


def run_task(stg: StrategyConfig):
    # run as long as the task is not cancelled
    asyncio.run(task_context.start_task(stg))


async def stop_task(sha: str):
    await task_context.cancel_task(sha)
    pub.publish_message(sha, f"{sha} stopped")


async def stop_all_tasks():
    n = await task_context.cancel_all()
    return n


def get_tasks():
    return task_context.get_tasks()
