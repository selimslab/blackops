import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.robots import robot_api
from src.api.routers.home import router as home_router
from src.api.routers.stg import router as stg_router
from src.api.routers.robot import router as robot_router

app = FastAPI(title="BlackOps API", docs_url="/docs", redoc_url="/redoc")

app.mount("/panel", StaticFiles(directory="static", html=True), name="panel")

app.include_router(stg_router, prefix="/stg", tags=["Strategy"])
app.include_router(robot_router, prefix="/robot", tags=["Robot"])
app.include_router(home_router, tags=["Home"])


@app.exception_handler(Exception)
async def validation_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


@app.on_event("shutdown")
async def shutdown_event():
    await robot_api.stop_all_tasks()


if __name__ == "__main__":
    uvicorn.run(app)