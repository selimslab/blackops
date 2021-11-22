import asyncio
import itertools
import time
from datetime import datetime
from typing import Any, Callable, List, Union

from celery import Celery
from celery.states import PENDING, SUCCESS, state

import blackops.pubsub.push_events as event
from blackops.api.models.stg import Strategy
from blackops.pubsub.push import pusher_client
from blackops.taskq.redis import redis_url
from blackops.trader.factory import create_trader_from_strategy
from blackops.util.logger import logger

app = Celery(
    "celery-leader",
    include=["blackops.taskq.tasks"],
    broker=redis_url,
    backend=redis_url,
)


def revoke(task_id: Union[str, List[str]]) -> Any:
    return app.control.revoke(task_id, terminate=True, signal="SIGUSR1")


def get_result(task_id: str) -> Any:
    return app.AsyncResult(task_id).result


@app.task
def greet(name: str) -> str:
    time.sleep(5)
    return "hello " + name


@app.task
async def testrun():
    i = 0
    while True:
        asyncio.sleep(1)
        print(i)
        i += 1


async def run_stg_async(stg: dict):
    trader = await create_trader_from_strategy(stg)
    if trader:
        await asyncio.create_task(trader.run())


@app.task(serializer="json", acks_late=True)
def run_stg(stg: dict):
    try:
        asyncio.run(run_stg_async(stg))
    except Exception as e:
        message = {
            "type": "error",
            "message": str(e),
            "time": str(datetime.now().time()),
        }
        pusher_client.trigger(stg.get("sha"), event.update, message)


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

    return started_task.id


def flatten(ll):
    return list(itertools.chain.from_iterable(ll))


def revoke_all():
    # Inspect all nodes.
    i = app.control.inspect()

    # Show the items that have an ETA or are scheduled for later processing

    task_lists = [i.scheduled().values(), i.reserved().values(), i.active().values()]
    task_lists = flatten(task_lists)

    print(task_lists, task_lists)

    ids = [task.get("id") for tl in task_lists for task in tl]
    ids = [i for i in ids if i]

    for i in ids:
        revoke(i)


if __name__ == "__main__":
    app.start()
