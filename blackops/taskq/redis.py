import os

import aioredis
import redis

from blackops.util.logger import logger

redis_host = os.getenv("REDIS_HOST", "NO REDIS")

logger.info(f"redis_hostl: {redis_host}")

# single instance
# aio_redis_client: aioredis.Redis = aioredis.from_url(redis_url)

redis_client = redis.Redis(host=redis_host, port=6379)
