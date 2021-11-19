from typing import Any, Callable, List, Union

from celery import Celery
from celery.states import PENDING, SUCCESS, state

from .redis import redis_client, redis_url

app = Celery("tasks", broker=redis_url, backend=redis_url)


def get_status(task_id: str) -> str:
    return app.AsyncResult(task_id).state


def revoke(task_id: Union[str, List[str]]) -> Any:
    return app.control.revoke(task_id, terminate=True)


def get_result(task_id: str) -> Any:
    return app.AsyncResult(task_id).result


def is_in_progress(current_running_task_id):
    return current_running_task_id and get_status(
        str(current_running_task_id, encoding="utf-8")
    ) in ["STARTED", "RETRY", "PENDING"]


async def start_task(concurrency_key: str, start_task_func: Callable) -> str:
    concurrency_key = concurrency_key.lower()

    with redis_client.lock(concurrency_key, timeout=10):
        current_running_task_id = redis_client.get(concurrency_key)

        if current_running_task_id and is_in_progress(current_running_task_id):
            raise Exception(
                f"Task already in progress for {concurrency_key} with id {current_running_task_id}"
            )

        started_task = start_task_func()
        redis_client.set(concurrency_key, started_task.id)
        return str(started_task.id)
