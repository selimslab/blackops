from datetime import datetime
from typing import List

import simplejson as json  # type: ignore
from fastapi import HTTPException

import blackops.pubsub.pub as pub
from blackops.domain.asset import Asset, AssetPair
from blackops.exchanges.btcturk import btc_real_api_client_public
from blackops.robots.config import StrategyConfig
from blackops.taskq.redis import async_redis_client
from blackops.taskq.task_ctx import task_context
from blackops.util.hash import dict_to_hash
from blackops.util.logger import logger

STG_MAP = "STG_MAP"


async def list_stgs() -> List[dict]:
    stgs = await async_redis_client.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


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

    pair = AssetPair(Asset(symbol=stg.base), Asset(symbol=stg.quote))
    ticker = await btc_real_api_client_public.get_ticker(pair)
    if not ticker:
        raise Exception("couldn't read price, please try again")
    stg.reference_price_for_parameters = ticker
    stg.set_params_auto()

    stg.is_valid()

    # hash all but sha field, which is used as the key
    sha = dict_to_hash(stg.dict(exclude={"sha", "created_at"}))[:7]

    stg.sha = sha
    stg.created_at = str(datetime.now().isoformat())

    if not await async_redis_client.hexists(STG_MAP, stg.sha):
        await async_redis_client.hset(STG_MAP, stg.sha, json.dumps(stg.dict()))

    return stg
