from blackops.taskq.redis import redis_client 
import asyncio 

async def sub():
    p = redis_client.pubsub()
    p.subscribe("test")
    while True:
        m = p.get_message()
        print(m)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(sub())