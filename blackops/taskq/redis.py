import aioredis

redis_url = "redis://localhost:6379"

# single instance
redis: aioredis.Redis = aioredis.from_url(redis_url)
