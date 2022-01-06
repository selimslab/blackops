from src.robots.context import robot_context


def get_orders(sha: str) -> list:
    return robot_context.get_orders(sha)
