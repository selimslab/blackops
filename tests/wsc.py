from fastapi_websocket_pubsub import PubSubClient
# Callback to be called upon event being published on server
import asyncio


async def on_event(data):
    print("We got an event! with data- ", data)

async def client():
    async with PubSubClient(server_uri="ws://localhost:8000/pubsub") as client:
        # Subscribe for the event 
        
        client.subscribe("triggered", on_event)


asyncio.run(client())
