import hashlib
import secrets
from typing import OrderedDict

import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from blackops.api.models.stg import STG_MAP, Strategy

from .task_ctx import context

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")
security = HTTPBasic()

app.mount("/logs", StaticFiles(directory="static", html=True), name="logs")
templates = Jinja2Templates(directory="templates")


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
async def root():
    # return JSONResponse(content={"message": "Hello, world!"})
    return FileResponse("static/index.html")
    # return templates.TemplateResponse("item.html", {"request": "pong"})


@app.put(
    "/run/",
    tags=["run"],
)
async def run_stg(
    stg: Strategy, background_tasks: BackgroundTasks, auth: bool = Depends(auth)
):
    """
    This will run the strategy with your parameters

    1. Click `try it out` button to open parameter editor.

    2. Edit your params, please do not delete commas or quotes, yet don't worry, if its not valid, it will warn you when you click execute

    3. Click on `execute` button to validate your params and start the strategy.

    4. If ok, you will see a task id in the response.

    5. View logs on `/logs` url
    """
    # stg = await get_stg(sha)

    stg.is_valid()

    stg_dict = dict(stg)

    sha = dict_to_hash(stg_dict)

    if sha in context.tasks:
        raise Exception("Task already running o")

    stg_dict["sha"] = sha

    background_tasks.add_task(context.start_task, stg_dict)

    return JSONResponse(content={"ok": f"task started with id {sha}"})


@app.put("/stop/{sha}", tags=["stop"])
async def stop_stg(sha: str, auth: bool = Depends(auth)):
    """
    Copy and paste the sha from the response of run_stg to stop the task.
    """
    await context.cancel_task(sha)
    return JSONResponse(content={"message": f"stopped task {sha}"})


@app.put("/stop/all", tags=["stop"])
async def stop_stg_all(auth: bool = Depends(auth)):
    """
    Stop all running tasks
    """
    await context.cancel_all()
    return JSONResponse(content={"message": f"stopped all"})
