from dataclasses import astuple, dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Mapping, Optional, OrderedDict, Union

import simplejson as json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic.errors import DataclassTypeError

import blackops.taskq.tasks as taskq
from blackops.taskq.redis import redis

from .stg import STG_MAP, Strategy

app = FastAPI()


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


async def get_stg(hash: str):
    print(hash, type(hash))
    stg = await redis.hget(STG_MAP, hash)
    if not stg:
        raise HTTPException(status_code=404, detail="no such stg")
    return json.loads(stg, object_pairs_hook=OrderedDict)


async def list_stgs() -> List[dict]:
    stgs = await redis.hvals(STG_MAP)
    return [json.loads(s) for s in stgs]


async def stop_all():
    stgs = await list_stgs()
    if stgs:
        hashes = [s.get("hash", "") for s in stgs]
        taskq.revoke(hashes)


@app.get("/")
async def read_root():
    return taskq.greet(name="selim")



@app.put("/stg/", response_model=Strategy)
async def create_stg(stg: Strategy):
    """Create a new stg. A stg is immutable. Creating will not run it yet. Review and run"""

    stg.is_valid()
    
    st = await redis.hexists(STG_MAP, stg.hash)
    print(st, stg.hash, type(stg.hash))
    if st:
        raise HTTPException(status_code=403, detail="stg already exists")

    await redis.hset(STG_MAP, stg.hash, stg.to_json_str())

    return stg


@app.get("/stg/{hash}")
async def read_stg(hash: str):
    """View the stg with this id"""
    return await get_stg(hash)

@app.delete("/stg/{hash}")
async def delete_stg(hash: str):
    """Delete the stg with this id"""
    await redis.hdel(STG_MAP, hash)
    taskq.revoke(hash)
    return JSONResponse(content={"message": f"removed {hash}"})


@app.put("/stg/{hash}", response_model=Strategy)
async def run_stg(hash: str):
    stg = await get_stg(hash)

    def task():
        return taskq.run_stg.delay(json.loads(stg))

    task_id = taskq.start_task(hash, task)

    return task_id


@app.put("/stg/{hash}")
async def stop_stg(hash: str):
    taskq.revoke(hash)
    return JSONResponse(content={"message": f"stopped {hash}"})


## Multiples

@app.get("/stgs/", response_model=List[Union[Strategy, dict]])
async def list_strategies():
    """View all strategies"""
    stgs = await list_stgs()
    if stgs:
        return stgs
    raise HTTPException(status_code=404, detail="no stg yet")



@app.delete("/stgs/")
async def delete_all_strategies():
    """Delete all strategies"""
    await redis.hdel(STG_MAP)
    await stop_all()
    return JSONResponse(content={"message": "removed all"})


@app.put("/stgs/stop_all")
async def stop_all_strategies():
    await stop_all()
    return JSONResponse(content={"message": "stopped all"})

