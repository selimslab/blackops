from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

import blackops.api.route_handlers.task as task_handler
from blackops.api.auth import auth

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/")
async def get_all_tasks():
    return task_handler.get_tasks()


@router.put("/{sha}")
async def run_task(
    sha: str, background_tasks: BackgroundTasks, timeout_seconds: int = 3600
):
    """
    When you give a sha, this will run the given strategy

    1. If ok, you will see a task id in the response.

    5. View logs on the home page
    """
    stg = await task_handler.deserialize_stg_config(sha)
    background_tasks.add_task(task_handler.run_task, (stg, timeout_seconds))
    return JSONResponse(content={"message": f"started strategy {sha}"})


# @router.get("/")
# async def get_all_tasks():
#     return taskq.get_result_all()


# @router.get("/{sha}")
# async def get_task(sha: str):
#     task_id = await handlers.get_task_id(sha)
#     return taskq.get_result(task_id)


@router.delete("/")
async def stop_all_tasks():
    n = await task_handler.stop_all_tasks()
    return JSONResponse(content={"message": f"stopped {n} tasks"})


@router.delete("/{sha}")
async def stop_task(sha: str):
    await task_handler.stop_task(sha)
    return JSONResponse(content={"message": f"stopped {sha}"})
