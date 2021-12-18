from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

import blackops.api.route_handlers.order as order_handler
from blackops.api.auth import auth

router = APIRouter(dependencies=[Depends(auth)])


@router.get("/{sha}")
def get_orders(sha: str):
    return order_handler.get_orders(sha)
