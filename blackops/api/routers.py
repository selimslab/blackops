from typing import List, Union

import simplejson as json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

import blackops.api.handlers as handlers
import blackops.taskq.tasks as taskq
from blackops.api.models.stg import Strategy

from .auth import auth

router = APIRouter()


@router.get("/stg/", response_model=List[Union[Strategy, dict]], tags=["read"])
async def list_strategies(auth: bool = Depends(auth)):
    """View all strategies"""
    stgs = await handlers.list_stgs()
    if stgs:
        return stgs
    raise HTTPException(status_code=404, detail="no stg yet")


@router.get("/stg/{sha}", tags=["read"])
async def read_stg(sha: str, auth: bool = Depends(auth)):
    """View the stg with this id"""
    return await handlers.get_stg(sha)


@router.put("/stg/", response_model=dict, tags=["create"])
async def create_stg(stg: Strategy, auth: bool = Depends(auth)):
    """Create a new stg.
    A stg is immutable.
    Creating will not run it yet.
    Make sure its correct,
    then use the sha to run it
    """

    return await handlers.create_stg(stg)


@router.put("/stg/run/{sha}", tags=["run"])
async def run_stg(sha: str, auth: bool = Depends(auth)) -> str:
    """
    This will run the strategy with your parameters

    1. Click `try it out` button to open parameter editor.

    2. Edit your params, please do not delete commas or quotes, yet don't worry, if its not valid, it will warn you when you click execute

    3. Click on `execute` button to validate your params and start the strategy.

    4. If ok, you will see a task id in the response.

    5. View logs on `/logs` url
    """
    return await handlers.run_stg(sha)


@router.put("/stg/stop/{task_id}", tags=["stop"])
async def stop_stg(task_id: str, auth: bool = Depends(auth)):
    taskq.revoke(task_id)
    return JSONResponse(content={"message": f"stopped {task_id}"})


@router.put("/stg/stop/all", tags=["stop"])
async def stop_all_strategies(auth: bool = Depends(auth)):
    await handlers.stop_all()
    return JSONResponse(content={"message": "stopped all"})
