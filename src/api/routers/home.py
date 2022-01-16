from fastapi import APIRouter, Depends, FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse

from src.api.auth import auth

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/")
async def root():
    return FileResponse("static/index.html")


# @router.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     while True:
#         # data = await websocket.receive_text()
#         await websocket.send_json({"hello": "world"})
#         await asyncio.sleep(1)
