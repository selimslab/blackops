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
    config: dict = await get_stg(sha)
    stg_dict: dict = config.get("config", {})

    # deserialize dict to config
    stg_type = StrategyType(stg_dict.get("type"))

    config_class = STRATEGY_CLASS[stg_type]

    stg: StrategyConfig = config_class(**stg_dict)

    return stg


def run_task(stg: StrategyConfig):
    # asyncio.run(start_task(sha))
    # await create_log_channel(sha)

    task_context.start_task(stg)
    # task_id = await taskq.start_task(sha, task_func)
    # await async_redis_client.hset(RUNNING_TASKS, sha, task_id)
    # await async_redis_client.sadd("RUNNING_TASKS", sha)
    return stg.sha


async def stop_task(sha: str):
    await task_context.cancel_task(sha)
    pub.publish_message(sha, f"{sha} stopped")


async def stop_all_tasks():

    # stgs = await list_stgs()
    # if stgs:
    #     hashes = [s.get("sha", "") for s in stgs]
    #     task_ids = await async_redis_client.mget(hashes)
    #     taskq.revoke(task_ids)

    # taskq.revoke_all()

    n = await task_context.cancel_all()
    return n


def get_tasks():
    return task_context.get_tasks()
