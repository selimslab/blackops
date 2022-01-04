from typing import Tuple

from blackops.robots.config import StrategyConfig, StrategyType
from blackops.robots.sliding.factory import sliding_window_factory
from blackops.robots.sliding.main import SlidingWindowTrader
from blackops.robots.watchers import BalanceWatcher, BookWatcher
from blackops.util.logger import logger

Robot = SlidingWindowTrader  # union type

FACTORIES = {
    StrategyType.SLIDING_WINDOW: sliding_window_factory,
}


def create_trader_from_strategy(
    stg: StrategyConfig,
) -> Tuple[SlidingWindowTrader, BalanceWatcher, BookWatcher]:
    try:
        stg.is_valid()
        factory_func = FACTORIES[StrategyType(stg.type)]
        return factory_func(stg)
    except Exception as e:
        logger.error(f"create_trader_from_strategy: {e}")
        raise e
