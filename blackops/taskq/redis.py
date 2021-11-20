import os

import aioredis
import redis  # type: ignore

from blackops.util.logger import logger

redis_host = os.environ.get("REDIS_HOST", "NOT SET")

logger.info(f"redis_host: {redis_host}")

redis_port = 6379

redis_url = f"{redis_host}:{redis_port}"


# single instance
#
redis_client: aioredis.Redis = aioredis.from_url(redis_url)

# redis_client = redis.Redis.from_url(redis_url)
