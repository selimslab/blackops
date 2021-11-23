from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

import blackops.api.handlers as handlers
from blackops.api.auth import auth

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/{sha}")
def get_orders(sha: str):
    return handlers.get_orders(sha)
