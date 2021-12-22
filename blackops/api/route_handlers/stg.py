from datetime import datetime
from typing import List

import simplejson as json  # type: ignore
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
from blackops.util.hash import dict_to_hash
from blackops.util.logger import logger


async def list_stgs() -> List[dict]:
    stgs = await async_redis_client.hvals(STG_MAP)
    stgs = [json.loads(s) for s in stgs]
    # if stgs:
    #     sorted_by_date = sorted(
    #         stgs,
    #         key=lambda stg: datetime.strptime(
    #             stg.get("created_at", ""), "%Y-%m-%dT%H:%M:%S.%f"
    #         ),
    #         reverse=True,
    #     )
    #     return sorted_by_date
    # else:
    return stgs


async def get_stg(sha: str) -> dict:
    stg = await async_redis_client.hget(STG_MAP, sha)
    if stg:
        return json.loads(stg)
    raise HTTPException(status_code=404, detail="Strategy not found")


async def delete_all_stg():
    await async_redis_client.delete(STG_MAP)


async def delete_stg(sha: str):
    if await async_redis_client.hexists(STG_MAP, sha):
        await async_redis_client.hdel(STG_MAP, sha)
    else:
        raise ValueError("stg not found")


async def create_stg(stg: StrategyConfig) -> StrategyConfig:

    stg.is_valid()

    # hash all but sha field, which is used as the key
    sha = dict_to_hash(stg.dict(exclude={"sha", "created_at"}))[:7]

    stg.sha = sha
    stg.created_at = str(datetime.now().isoformat())

    if not await async_redis_client.hexists(STG_MAP, stg.sha):
        await async_redis_client.hset(STG_MAP, stg.sha, json.dumps(stg.dict()))

    return stg
