from datetime import datetime
from typing import List

import simplejson as json  # type: ignore
from fastapi import HTTPException

from pydantic.json import pydantic_encoder
from .base import StrategyType
from .sliding import SlidingWindowInput, SlidingWindowConfig
from src.storage.redis import async_redis_client
from dataclasses import dataclass


StrategyInput = SlidingWindowInput

StrategyConfig = SlidingWindowConfig

STRATEGY_CLASS = {StrategyType.SLIDING_WINDOW: SlidingWindowConfig}


@dataclass
class StrategyAPI:

    STG_MAP = "STG_MAP"

    async def list_stgs(self) -> List[dict]:
        stgs = await async_redis_client.hvals(self.STG_MAP)
        return [json.loads(s) for s in stgs]


    async def get_stg(self, sha: str) -> StrategyConfig:
        stg_dict = await async_redis_client.hget(self.STG_MAP, sha)
        if not stg_dict:
            raise HTTPException(status_code=404, detail="Strategy not found")

        stg_type = StrategyType(stg_dict.get("type"))

        STG_CLASS = STRATEGY_CLASS[stg_type]

        stg: StrategyConfig = STG_CLASS(**stg_dict)
        return stg


    async def delete_all_stg(self):
        await async_redis_client.delete(self.STG_MAP)


    async def delete_stg(self,sha: str):
        if await async_redis_client.hexists(self.STG_MAP, sha):
            await async_redis_client.hdel(self.STG_MAP, sha)
        else:
            raise ValueError("stg not found")


    async def create_stg(self, stg: StrategyInput) -> StrategyConfig:
        stg_config = StrategyConfig(input=stg)

        if not await async_redis_client.hexists(self.STG_MAP, stg_config.sha):
            await async_redis_client.hset(self.STG_MAP, stg_config.sha, json.dumps(stg_config, default=pydantic_encoder))

        return stg_config


strategy_api = StrategyAPI()