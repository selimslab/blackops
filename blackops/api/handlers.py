import asyncio
import hashlib
import secrets
from typing import List, OrderedDict, Union

import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status

import blackops.taskq.tasks as taskq
from blackops.api.models.stg import STG_MAP, Strategy
from blackops.taskq.redis import redis_client
from blackops.taskq.task_ctx import task_context
from blackops.trader.factory import create_trader_from_strategy


def dict_to_hash(d: dict) -> str:
    return hashlib.sha1(json.dumps(d).encode()).hexdigest()


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


async def stop_all():
    # BUG
    stgs = await list_stgs()
    if stgs:
        hashes = [s.get("sha", "") for s in stgs]
        task_ids = await redis_client.mget(hashes)
        taskq.revoke(task_ids)


async def run_stg(sha: str) -> str:
    stg: dict = await get_stg(sha)

    def task_func():
        return taskq.run_stg.delay(stg)

    task_id = await taskq.start_task(sha, task_func)

    return task_id
