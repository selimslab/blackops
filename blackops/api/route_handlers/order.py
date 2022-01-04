from blackops.taskq.task_ctx import task_context


def get_orders(sha: str) -> list:
    return task_context.get_orders(sha)
