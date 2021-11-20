import asyncio
import time
from typing import Any, Callable, List, Union

from celery import Celery
from celery.states import PENDING, SUCCESS, state

from blackops.api.models.stg import Strategy
from blackops.taskq.redis import redis_client, redis_url
from blackops.trader.factory import create_trader_from_strategy
from blackops.util.logger import logger

app = Celery(
    "celery-leader",
    broker=redis_url + "/0",
    backend=redis_url + "/0",
    include=["blackops.taskq.tasks"],
)


def revoke(task_id: Union[str, List[str]]) -> Any:
    return app.control.revoke(task_id, terminate=True)


def get_result(task_id: str) -> Any:
    return app.AsyncResult(task_id).result


@app.task
def greet(name: str) -> str:
    time.sleep(5)
    # raise Exception("Error")
    return "hello " + name


@app.task
def run_stg(stg: dict):
    trader = create_trader_from_strategy(stg)
    if trader:
        asyncio.run(trader.run())  # type: ignore


def get_status(task_id: str) -> str:
    return app.AsyncResult(task_id).state


def is_in_progress(task_id):
    return get_status(task_id) in ["STARTED", "RETRY", "PENDING"]


async def start_task(sha: str, start_task_func: Callable) -> str:

    # async with redis_client.lock(sha, timeout=10):
    #     current_running_task_id = await redis_client.get(sha)
    #     if current_running_task_id:
    #         current_running_task_id = current_running_task_id.decode("utf-8")

    #     logger.info(f"current_running_task_id: {current_running_task_id}")
    #     if current_running_task_id and is_in_progress(current_running_task_id):
    #         raise Exception(
    #             f"Task already in progress"
    #         )

    started_task = start_task_func()

    # add task id to redis
    await redis_client.set(sha, started_task.id)
    return started_task.id


if __name__ == "__main__":
    app.start()
