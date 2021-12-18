import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from blackops.api.routers.order import router as order_router
from blackops.api.routers.stg import router as stg_router
from blackops.api.routers.task import router as task_router

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")

app.include_router(stg_router, prefix="/stg", tags=["Strategy"])
app.include_router(task_router, prefix="/task", tags=["Task"])
app.include_router(order_router, prefix="/order", tags=["Order"])


app.mount("/logs", StaticFiles(directory="static", html=True), name="logs")


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


@app.get("/monitor/")
async def logs():
    return FileResponse("static/logs.html")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    uvicorn.run(app)
