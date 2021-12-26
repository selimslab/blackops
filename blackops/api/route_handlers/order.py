from fastapi import HTTPException

import blackops.pubsub.pub as pub
from blackops.robots.config import STRATEGY_CLASS, StrategyConfig, StrategyType
from blackops.taskq.redis import (
    LOG_CHANNELS,
    RUNNING_TASKS,
    STG_MAP,
    async_redis_client,
)
from blackops.taskq.task_ctx import task_context


def get_orders(sha: str) -> list:
    return task_context.get_orders(sha)
