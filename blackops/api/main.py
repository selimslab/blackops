import asyncio
import hashlib
import secrets
from typing import List, OrderedDict, Union

import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.param_functions import File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic.errors import DataclassTypeError

import blackops.taskq.tasks as taskq
from blackops.api.models.stg import STG_MAP, Strategy
from blackops.trader.factory import create_trader_from_strategy

app = FastAPI()
security = HTTPBasic()

app.mount("/static", StaticFiles(directory="static", html=True), name="static")


def auth(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "3924")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


def dict_to_hash(d: dict) -> str:
    return hashlib.sha1(json.dumps(d).encode()).hexdigest()


def str_to_json(s: str) -> dict:
    return json.loads(s, object_pairs_hook=OrderedDict)


class TaskContext:
    def __init__(self):
        self.tasks = {}

    async def start_task(self, stg: dict):
        sha = stg.get("sha")
        if sha in self.tasks:
            raise Exception("Task already running")
        trader = await create_trader_from_strategy(stg)
        task = asyncio.create_task(trader.run())
        self.tasks[sha] = task
        await task

    async def cancel_task(self, sha):
        if sha in self.tasks:
            self.tasks[sha].cancel()
            del self.tasks[sha]
        else:
            raise Exception("Task not found")


context = TaskContext()


@app.put(
    "/stg/run/",
    tags=["run"],
)
async def run_stg(
    stg: Strategy, background_tasks: BackgroundTasks, auth: bool = Depends(auth)
):
    # stg = await get_stg(sha)

    stg.is_valid()

    stg_dict = dict(stg)

    sha = dict_to_hash(stg_dict)

    if sha in context.tasks:
        raise Exception("Task already running o")

    stg_dict["sha"] = sha

    background_tasks.add_task(context.start_task, stg_dict)

    return JSONResponse(content={"ok": f"task started with id {sha}"})


@app.put("/stg/stop/{sha}", tags=["stop"])
async def stop_stg(sha: str, auth: bool = Depends(auth)):
    # taskq.revoke(task_id)
    await context.cancel_task(sha)
    return JSONResponse(content={"message": f"stopped task {sha}"})
