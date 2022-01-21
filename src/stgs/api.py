from dataclasses import dataclass
from decimal import Decimal
from typing import List

import simplejson as json  # type: ignore
from fastapi import HTTPException
from pydantic.json import pydantic_encoder

from src.domain import Asset, AssetPair
from src.exchanges.btcturk import btc_real_api_client_public
from src.storage.redis import async_redis_client

from .base import StrategyType
from .sliding.config import LeaderFollowerConfig, LeaderFollowerInput

StrategyInput = LeaderFollowerInput

StrategyConfig = LeaderFollowerConfig

STRATEGY_INPUT_CLASS = {StrategyType.SLIDING_WINDOW: LeaderFollowerInput}

STRATEGY_CONFIG_CLASS = {StrategyType.SLIDING_WINDOW: LeaderFollowerConfig}


@dataclass
class StrategyAPI:

    STG_MAP = "STG_MAP"

    async def list_stgs(self) -> List[dict]:
        stgs = await async_redis_client.hvals(self.STG_MAP)
        return [json.loads(s) for s in stgs]

    async def get_stg(self, sha: str) -> StrategyConfig:
        stg_str = await async_redis_client.hget(self.STG_MAP, sha)
        if not stg_str:
            raise HTTPException(status_code=404, detail="Strategy not found")

        stg_dict = json.loads(stg_str)
        stg_type = StrategyType(stg_dict.get("type"))

        STG_CLASS = STRATEGY_INPUT_CLASS[stg_type]
        stg: StrategyInput = STG_CLASS(**stg_dict)

        stg_config = await self.stg_to_config(stg)
        return stg_config

    async def delete_all_stg(self):
        await async_redis_client.delete(self.STG_MAP)

    async def delete_stg(self, sha: str):
        if await async_redis_client.hexists(self.STG_MAP, sha):
            await async_redis_client.hdel(self.STG_MAP, sha)
        else:
            raise ValueError("stg not found")

    async def get_ticker(self, pair: AssetPair) -> Decimal:

        ticker = await btc_real_api_client_public.get_ticker(pair)
        if not ticker:
            raise Exception("couldn't read price, please try again")

        return ticker

    async def stg_to_config(self, stg: StrategyInput) -> StrategyConfig:
        pair = AssetPair(base=Asset(symbol=stg.base), quote=Asset(symbol=stg.quote))

        # ticker = await self.get_ticker(pair)

        stg_config = StrategyConfig(input=stg)

        return stg_config

    async def create_stg(self, stg: StrategyInput) -> StrategyConfig:

        stg_config = await self.stg_to_config(stg)

        # overwrite if exists
        await async_redis_client.hset(
            self.STG_MAP, stg_config.sha, json.dumps(stg.dict())
        )

        return stg_config


strategy_api = StrategyAPI()
