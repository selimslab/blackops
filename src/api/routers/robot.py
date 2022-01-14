from typing import List

import aiohttp
import starlette.background as bg
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from src.api.auth import auth
from src.flow import flow_api
from src.stgs import strategy_api

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/")
async def get_all():
    return flow_api.get_tasks()


@router.post("/{sha}")
async def run(sha: str, background_tasks: BackgroundTasks):
    """
    When you give a sha, this will run the given strategy

    1. If ok, you will see a task id in the response.

    5. View logs on the home page
    """
    flow_api.is_running(sha)

    stg = await strategy_api.get_stg(sha)

    background_tasks.add_task(flow_api.run_task, stg)
    return JSONResponse(content={"message": f"started strategy {sha}"})


@router.delete("/{sha}")
async def stop(sha: str):
    await flow_api.stop_task(sha)
    return JSONResponse(content={"message": f"stopped {sha}"})


@router.post("/")
async def run_multiple(shas: List[str]):
    async with aiohttp.ClientSession() as session:
        for sha in shas:
            await session.post(
                f"http://0.0.0.0:80/robot/{sha}",
                headers={"Authorization": "Basic c2VyZW5pdHk6ZmVlbHBsYW5nbw=="},
            )
    return JSONResponse(content={"message": f"started {shas}"})


@router.delete("/")
async def stop_all():
    stopped_shas = await flow_api.stop_all_tasks()
    return JSONResponse(content={"message": f"stopped {stopped_shas}"})
