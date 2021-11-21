import simplejson as json
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import router

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")

app.include_router(router)


app.mount("/logs", StaticFiles(directory="static", html=True), name="logs")


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


@app.get("/")
async def root():
    return FileResponse("static/index.html")
