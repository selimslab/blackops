from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import auth
from src.monitoring import logger
from src.stgs import StrategyConfig, StrategyInput, strategy_api

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/", response_model=list)
async def read_all():
    """View all strategies"""
    stgs = await strategy_api.list_stgs()
    if stgs:
        return stgs
        # shas = [stg.get("sha") for stg in stgs]
        # return [s for s in shas if s]
    raise HTTPException(status_code=404, detail="no stg yet")


@router.get("/{sha}")
async def read(sha: str):
    """View the stg with this id"""
    return await strategy_api.get_stg(sha)


@router.delete("/", response_model=dict)
async def delete_all():
    """Delete a strategy"""
    return await strategy_api.delete_all_stg()


@router.delete("/{sha}", response_model=dict)
async def delete(
    sha: str,
):
    """Delete a strategy"""
    return await strategy_api.delete_stg(sha)


@router.put(
    "/",
    response_model=StrategyConfig,
)
async def create(stg: StrategyInput):
    """
    This will run the strategy with your parameters

    1. Click `try it out` button to open parameter editor.

    2. Edit your params, please do not delete commas or quotes, yet don't worry, if its not valid, it will warn you when you click execute

    3. Click on `execute` button to validate your params and save the strategy

    4. Saving will not run it, you can copy paste the sha in response to /run endpoint to start the strategy

    """

    return await strategy_api.create_stg(stg)
