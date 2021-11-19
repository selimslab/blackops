import aioredis
import redis

redis_url = "redis:6379"

# single instance
aio_redis_client: aioredis.Redis = aioredis.from_url(redis_url)

redis_client = redis.Redis(host="redis", port=6379)
