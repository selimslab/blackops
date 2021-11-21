import hashlib
import secrets
from typing import List, OrderedDict, Union

import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .routers import router

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")

app.include_router(router)


app.mount("/logs", StaticFiles(directory="static", html=True), name="logs")
templates = Jinja2Templates(directory="templates")


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


@app.get("/")
async def root():
    # return JSONResponse(content={"message": "Hello, world!"})
    return FileResponse("static/index.html")
    # return templates.TemplateResponse("item.html", {"request": "pong"})
