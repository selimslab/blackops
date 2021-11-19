import os

import redis  # type: ignore

from blackops.util.logger import logger

redis_host = os.environ.get("REDIS_HOST", "http://localhost")

logger.info(f"redis_host: {redis_host}")

redis_port = 6379

redis_url = f"{redis_host}:{redis_port}"

redis_url = redis_host + ":" + str(redis_port)

# single instance
# aio_redis_client: aioredis.Redis = aioredis.from_url(redis_url)

redis_client = redis.Redis(host=redis_host, port=redis_port)
