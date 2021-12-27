from typing import Callable

from blackops.robots.config import StrategyConfig, StrategyType
from blackops.robots.sliding.factory import sliding_window_factory
from blackops.robots.sliding.main import SlidingWindowTrader
from blackops.util.logger import logger

Robot = SlidingWindowTrader  # union type

FACTORIES = {
    StrategyType.SLIDING_WINDOW: sliding_window_factory,
}


def create_trader_from_strategy(stg: StrategyConfig) -> Robot:
    try:
        stg.is_valid()
        factory_func = FACTORIES[StrategyType(stg.type)]
        robot = factory_func(stg)
        return robot
    except Exception as e:
        logger.error(f"create_trader_from_strategy: {e}")
        raise e
