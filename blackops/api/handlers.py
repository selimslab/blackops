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


def dict_to_hash(d: dict) -> str:
    return hashlib.md5(json.dumps(d).encode()).hexdigest()


def str_to_json(s: str) -> dict:
    return json.loads(s, object_pairs_hook=OrderedDict)


async def list_stgs() -> List[dict]:
    stgs = await async_redis_client.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


async def get_stg(sha: str) -> dict:
    stg = await async_redis_client.hget(STG_MAP, sha)
    if stg:
        return json.loads(stg)
    raise HTTPException(status_code=404, detail="Strategy not found")


async def delete_stg(sha: str):
    if await async_redis_client.hexists(STG_MAP, sha):
        await async_redis_client.hdel(STG_MAP, sha)
    else:
        raise ValueError("stg not found")


async def delete_all():
    await async_redis_client.delete(STG_MAP)


async def create_stg(stg: StrategyConfig) -> dict:

    stg.is_valid()

    d = stg.dict()

    sha = dict_to_hash(d)[:7]
    d["sha"] = sha

    # if you ever need a uid ,its important to hash it without uid for the idempotency of stg
    # uid = str(uuid.uuid4())
    # d["uid"] = uid

    if await async_redis_client.hexists(STG_MAP, sha):
        raise HTTPException(status_code=403, detail="stg already exists")

    await async_redis_client.hset(STG_MAP, sha, json.dumps(d))

    return d


async def get_task_id(sha):
    return await async_redis_client.hget(RUNNING_TASKS, sha)


async def run_task(sha: str):
    # asyncio.run(start_task(sha))
    # await create_log_channel(sha)
    stg_dict: dict = await get_stg(sha)

    # deserialize dict to config
    stg_type = StrategyType(stg_dict.get("type"))
    config_class = STRATEGY_CLASS[stg_type]
    stg: StrategyConfig = config_class(**stg_dict)

    task_context.start_task(stg)
    # task_id = await taskq.start_task(sha, task_func)
    # await async_redis_client.hset(RUNNING_TASKS, sha, task_id)
    # await async_redis_client.sadd("RUNNING_TASKS", sha)
    return sha


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


def get_orders(sha: str):
    return task_context.get_orders(sha)


def get_tasks():
    return task_context.get_tasks()
