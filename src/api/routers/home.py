import asyncio

from fastapi import APIRouter, Depends, FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse

from src.api.auth import auth
from src.monitoring import logger

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/")
async def root():
    return FileResponse("static/index.html")
