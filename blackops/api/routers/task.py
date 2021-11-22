import simplejson as json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import blackops.api.handlers as handlers
import blackops.taskq.tasks as taskq
from blackops.api.auth import auth
from blackops.api.models.stg import Strategy

router = APIRouter(dependencies=[Depends(auth)])


@router.put("/task/{sha}", tags=["run"])
async def run_task(sha: str):
    """
    When you give a sha, this will run the given strategy

    1. If ok, you will see a task id in the response.

    5. View logs on the home page
    """
    task_id = await handlers.run_stg(sha)
    return JSONResponse(
        content={"message": f"started strategy {sha} with task id {task_id}"}
    )


@router.delete("/task/", tags=["stop"])
async def stop_all_tasks():
    await handlers.stop_all()
    return JSONResponse(content={"message": "stopped all"})


@router.delete("/task/{sha}", tags=["stop"])
async def stop_task(sha: str):
    await handlers.stop_stg(sha)
    return JSONResponse(content={"message": f"stopped {sha}"})
