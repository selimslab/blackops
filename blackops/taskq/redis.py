import os

import aioredis
import redis  # type: ignore

from blackops.util.logger import logger

redis_url = os.environ["REDIS_URL"]

redis_client: aioredis.Redis = aioredis.from_url(redis_url)

# redis_client = redis.Redis.from_url(redis_url)
