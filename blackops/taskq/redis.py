import os

import aioredis
import redis  # type: ignore

from blackops.util.logger import logger

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

async_redis_client: aioredis.Redis = aioredis.from_url(redis_url)

redis_client = redis.Redis.from_url(redis_url)

STREAM_MAP = "STREAM_MAP"

STG_MAP = "STG_MAP"

RUNNING_TASKS = "RUNNING_TASKS"

LOG_CHANNELS = "LOG_CHANNELS"
