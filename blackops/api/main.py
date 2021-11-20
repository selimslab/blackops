import hashlib
import secrets
from typing import List, OrderedDict, Union

import simplejson as json
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from pydantic.errors import DataclassTypeError

import blackops.taskq.tasks as taskq
from blackops.api.models.stg import STG_MAP, Strategy
from blackops.taskq.redis import redis_client

app = FastAPI()
security = HTTPBasic()


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


@app.get("/")
async def welcome():
    return {"ping": "pong"}


# REST


async def list_stgs() -> List[dict]:
    stgs = await redis_client.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


@app.get("/stg/", response_model=List[Union[Strategy, dict]], tags=["read"])
async def list_strategies(auth: bool = Depends(auth)):
    """View all strategies"""
    stgs = await list_stgs()
    if stgs:
        return stgs
    raise HTTPException(status_code=404, detail="no stg yet")


async def get_stg(sha: str) -> dict:
    stg = await redis_client.hget(STG_MAP, sha)
    if stg:
        return json.loads(stg)
    else:
        raise HTTPException(status_code=404, detail="Strategy not found")


@app.get("/stg/{sha}", tags=["read"])
async def read_stg(sha: str, auth: bool = Depends(auth)):
    """View the stg with this id"""
    return await get_stg(sha)


@app.put("/stg/", response_model=dict, tags=["create"])
async def create_stg(stg: Strategy, auth: bool = Depends(auth)):
    """Create a new stg.
    A stg is immutable.
    Creating will not run it yet.
    Make sure its correct,
    then use the sha to run it
    """

    stg.is_valid()

    d = dict(stg)

    sha = dict_to_hash(d)
    d["sha"] = sha

    # if you ever need a uid ,its important to hash it without uid for the idempotency of stg
    # uid = str(uuid.uuid4())
    # d["uid"] = uid

    if await redis_client.hexists(STG_MAP, sha):
        raise HTTPException(status_code=403, detail="stg already exists")

    await redis_client.hset(STG_MAP, sha, json.dumps(d))

    return d


@app.put("/stg/run/{sha}", tags=["run"])
async def run_stg(sha: str, auth: bool = Depends(auth)) -> str:
    stg = await get_stg(sha)

    def task():
        return taskq.run_stg.delay(stg)

    task_id = await taskq.start_task(sha, task)

    return task_id


@app.put("/stg/stop/{task_id}", tags=["stop"])
async def stop_stg(task_id: str, auth: bool = Depends(auth)):
    taskq.revoke(task_id)
    return JSONResponse(content={"message": f"stopped {task_id}"})


async def stop_all():
    # BUG
    stgs = await list_stgs()
    if stgs:
        hashes = [s.get("sha", "") for s in stgs]
        task_ids = await redis_client.mget(hashes)
        taskq.revoke(task_ids)


@app.put("/stg/stop/all", tags=["stop"])
async def stop_all_strategies(auth: bool = Depends(auth)):
    await stop_all()
    return JSONResponse(content={"message": "stopped all"})


@app.delete("/stg/{sha}", tags=["remove"])
async def delete_stg(sha: str, auth: bool = Depends(auth)):
    """Delete the stg with this id, also stop it if its running"""
    await redis_client.hdel(STG_MAP, sha)
    await stop_stg(sha)
    return JSONResponse(content={"message": f"removed {sha}"})


@app.delete("/stg/", tags=["remove"])
async def delete_all_strategies(auth: bool = Depends(auth)):
    """Delete all strategies, this also stops any running ones"""
    await redis_client.delete(STG_MAP)
    await stop_all()
    return JSONResponse(content={"message": "removed all"})
