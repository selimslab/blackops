import os

import aioredis
import redis  # type: ignore

from blackops.util.logger import logger

redis_host = os.getenv("REDIS_HOST", "NO REDIS")

logger.info(f"redis_hostl: {redis_host}")

redis_port = 6379

redis_url = redis_host + ":" + str(redis_port)

# single instance
# aio_redis_client: aioredis.Redis = aioredis.from_url(redis_url)

redis_client = redis.Redis(host=redis_host, port=redis_port)
