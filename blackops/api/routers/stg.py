import simplejson as json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import blackops.api.handlers as handlers
import blackops.taskq.tasks as taskq
from blackops.api.auth import auth
from blackops.api.models.stg import Strategy

router = APIRouter(dependencies=[Depends(auth)])


templates = Jinja2Templates(directory="templates")


@router.get("/logs/")
async def logs():
    # return templates.TemplateResponse("logs.html", {"request": {}, "sha": sha})
    return FileResponse("static/logs.html")


@router.get("/stg/", response_model=list, tags=["read"])
async def read_stg_all():
    """View all strategies"""
    stgs = await handlers.list_stgs()
    if stgs:
        return stgs
    raise HTTPException(status_code=404, detail="no stg yet")


@router.get("/stg/{sha}", tags=["read"])
async def read_stg(sha: str):
    """View the stg with this id"""
    return await handlers.get_stg(sha)


@router.delete("/stg/all", response_model=dict, tags=["delete"])
async def delete_all():
    """Delete a strategy"""
    return await handlers.delete_all()


@router.delete("/stg/{sha}", response_model=dict, tags=["delete"])
async def delete_stg(
    sha: str,
):
    """Delete a strategy"""
    return await handlers.delete_stg(sha)


@router.put("/stg/", response_model=dict, tags=["create"])
async def create_stg(stg: Strategy):
    """
    This will run the strategy with your parameters

    1. Click `try it out` button to open parameter editor.

    2. Edit your params, please do not delete commas or quotes, yet don't worry, if its not valid, it will warn you when you click execute

    3. Click on `execute` button to validate your params and save the strategy

    4. Saving will not run it, you can copy paste the sha in response to /run endpoint to start the strategy

    """

    return await handlers.create_stg(stg)
