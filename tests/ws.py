import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.routing import APIRouter

from fastapi_websocket_pubsub import PubSubEndpoint
app =  FastAPI()
# Init endpoint
endpoint = PubSubEndpoint()
# register the endpoint on the app
endpoint.register_route(app, "/pubsub")

# Register a regular HTTP route
@app.get("/trigger")
async def trigger_events():
    # Upon request trigger an event
    await endpoint.publish(["triggered"])


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)