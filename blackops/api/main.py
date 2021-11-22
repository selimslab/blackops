import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from blackops.api.routers.stg import router as stg_router
from blackops.api.routers.task import router as task_router

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")

app.include_router(stg_router, prefix="/stg", tags=["Strategy"])
app.include_router(task_router, prefix="/task", tags=["Tasks"])


app.mount("/logs", StaticFiles(directory="static", html=True), name="logs")


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


templates = Jinja2Templates(directory="templates")


@app.get("/logs/")
async def logs():
    # return templates.TemplateResponse("logs.html", {"request": {}, "sha": sha})
    return FileResponse("static/logs.html")


@app.get("/")
async def root():
    return FileResponse("static/index.html")
