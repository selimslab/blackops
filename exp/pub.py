from blackops.taskq.redis import redis_client 
import asyncio 
import itertools

async def pub():
    p = redis_client.pubsub()
    for i in itertools.count(1000):
        redis_client.publish("test", str(i))
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(pub())
