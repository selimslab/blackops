import hashlib
import secrets
import uuid
from typing import List, OrderedDict, Union

import simplejson as json
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from pydantic.errors import DataclassTypeError

import blackops.taskq.taskq as taskq
import blackops.taskq.tasks as tasks
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


async def get_stg(hash: str):
    print(hash, type(hash))
    stg = redis_client.hget(STG_MAP, hash)
    if not stg:
        raise HTTPException(status_code=404, detail="no such stg")
    return json.loads(stg, object_pairs_hook=OrderedDict)


async def list_stgs() -> List[dict]:
    stgs = redis_client.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


async def stop_all():
    stgs = await list_stgs()
    if stgs:
        hashes = [s.get("hash", "") for s in stgs]
        taskq.revoke(hashes)


@app.get("/")
async def read_root():
    return {"ping": "pong"}


# REST
@app.get("/stg/", response_model=List[Union[Strategy, dict]], tags=["read"])
async def list_strategies(auth: bool = Depends(auth)):
    """View all strategies"""
    stgs = await list_stgs()
    if stgs:
        return stgs
    raise HTTPException(status_code=404, detail="no stg yet")


@app.get("/stg/{hash}", tags=["read"])
async def read_stg(hash: str, auth: bool = Depends(auth)):
    """View the stg with this id"""
    return await get_stg(hash)


@app.put("/stg/", response_model=dict, tags=["create"])
async def create_stg(stg: Strategy, auth: bool = Depends(auth)):
    """Create a new stg. A stg is immutable. Creating will not run it yet. Review and run"""

    stg.is_valid()

    d = dict(stg)
    uid = str(uuid.uuid4())
    d["uid"] = uid

    hash = dict_to_hash(d)
    d["hash"] = hash

    if redis_client.hexists(STG_MAP, hash):
        raise HTTPException(status_code=403, detail="stg already exists")

    redis_client.hset(STG_MAP, hash, json.dumps(d))

    return d


@app.delete("/stg/{hash}", tags=["remove"])
async def delete_stg(hash: str, auth: bool = Depends(auth)):
    """Delete the stg with this id, also stop it if its running"""
    redis_client.hdel(STG_MAP, hash)
    taskq.revoke(hash)
    return JSONResponse(content={"message": f"removed {hash}"})


@app.delete("/stg/", tags=["remove"])
async def delete_all_strategies(auth: bool = Depends(auth)):
    """Delete all strategies, this also stops any running ones"""
    redis_client.hdel(STG_MAP)
    await stop_all()
    return JSONResponse(content={"message": "removed all"})


# RPC


@app.put("/stg/run/{hash}", tags=["run"])
async def run(hash: str, auth: bool = Depends(auth)) -> str:
    stg = await get_stg(hash)

    def task():
        return tasks.run_stg.delay(json.loads(stg))

    task_id = await taskq.start_task(hash, task)

    return task_id


@app.put("/stg/stop/{hash}", tags=["stop"])
async def stop_stg(hash: str, auth: bool = Depends(auth)):
    taskq.revoke(hash)
    return JSONResponse(content={"message": f"stopped {hash}"})


@app.put("/stg/stop/all", tags=["stop"])
async def stop_all_strategies(auth: bool = Depends(auth)):
    await stop_all()
    return JSONResponse(content={"message": "stopped all"})
