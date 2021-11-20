import asyncio

async def go():
    for i in range(100):
        print(i)
        asyncio.sleep(0.2)




async def main():
    asyncio.create_task(go())


asyncio.run(main())
