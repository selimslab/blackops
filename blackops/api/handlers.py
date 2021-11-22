import hashlib
from typing import List, OrderedDict

import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status

import blackops.taskq.tasks as taskq
from blackops.api.models.stg import Strategy
from blackops.taskq.redis import redis_client
from blackops.taskq.task_ctx import task_context
from blackops.trader.factory import create_trader_from_strategy

STG_MAP = "STG_MAP"

RUNNING_TASKS = "RUNNING_TASKS"

LOG_CHANNELS = "LOG_CHANNELS"


def dict_to_hash(d: dict) -> str:
    return hashlib.md5(json.dumps(d).encode()).hexdigest()


def str_to_json(s: str) -> dict:
    return json.loads(s, object_pairs_hook=OrderedDict)


async def list_stgs() -> List[dict]:
    stgs = await redis_client.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


async def get_stg(sha: str) -> dict:
    stg = await redis_client.hget(STG_MAP, sha)
    if stg:
        return json.loads(stg)
    raise HTTPException(status_code=404, detail="Strategy not found")


async def delete_stg(sha: str):
    if await redis_client.hexists(STG_MAP, sha):
        await redis_client.hdel(STG_MAP, sha)
    raise ValueError("stg not found")


async def delete_all():
    await redis_client.delete(STG_MAP)


async def create_stg(stg: Strategy) -> dict:

    stg.is_valid()

    d = dict(stg)

    sha = dict_to_hash(d)
    d["sha"] = sha

    # if you ever need a uid ,its important to hash it without uid for the idempotency of stg
    # uid = str(uuid.uuid4())
    # d["uid"] = uid

    if await redis_client.hexists(STG_MAP, sha):
        raise HTTPException(status_code=403, detail="stg already exists")

    await redis_client.hset(STG_MAP, sha, json.dumps(d))

    return d


async def create_log_channel(sha: str):
    await redis_client.sadd(LOG_CHANNELS, sha)


async def remove_log_channel(sha: str):
    await redis_client.srem(LOG_CHANNELS, sha)


async def get_task_id(sha):
    return await redis_client.hget(RUNNING_TASKS, sha)


async def run_stg(sha: str) -> str:
    stg: dict = await get_stg(sha)

    def task_func():
        return taskq.run_stg.delay(stg)

    await create_log_channel(sha)
    task_id = await taskq.start_task(sha, task_func)
    await redis_client.hset(RUNNING_TASKS, sha, task_id)
    return task_id


async def stop_stg(sha: str):
    task_id = await get_task_id(sha)
    if not task_id:
        raise ValueError("no tasks found")
    taskq.revoke(str(task_id, "utf-8"))
    await remove_log_channel(sha)


async def stop_all():
    # stgs = await list_stgs()
    # if stgs:
    #     hashes = [s.get("sha", "") for s in stgs]
    #     task_ids = await redis_client.mget(hashes)
    #     taskq.revoke(task_ids)

    taskq.revoke_all()
