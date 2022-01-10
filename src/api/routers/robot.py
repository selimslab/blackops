from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from src.api.auth import auth
from src.robots import robot_api
from src.stgs import strategy_api

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/")
async def get_all_tasks():
    return robot_api.get_tasks()


@router.put("/{sha}")
async def run_task(sha: str, background_tasks: BackgroundTasks):
    """
    When you give a sha, this will run the given strategy

    1. If ok, you will see a task id in the response.

    5. View logs on the home page
    """
    stg = await strategy_api.get_stg(sha)
    background_tasks.add_task(robot_api.run_task, stg)
    return JSONResponse(content={"message": f"started strategy {sha}"})


@router.delete("/")
async def stop_all_tasks():
    stopped_shas = await robot_api.stop_all_tasks()
    return JSONResponse(content={"message": f"stopped {stopped_shas}"})


@router.delete("/{sha}")
async def stop_task(sha: str):
    await robot_api.stop_task(sha)
    return JSONResponse(content={"message": f"stopped {sha}"})
