from src.monitoring import logger
from src.robots.sliding.factory import sliding_window_factory
from src.robots.sliding.main import SlidingWindowTrader
from src.robots.watchers import BalanceWatcher, BookWatcher
from src.stgs import StrategyConfig, StrategyType

Robot = SlidingWindowTrader  # union type

FACTORIES = {
    StrategyType.SLIDING_WINDOW: sliding_window_factory,
}


def create_trader_from_strategy(
    stg: StrategyConfig,
) -> Robot:
    try:
        stg.is_valid()
        factory_func = FACTORIES[StrategyType(stg.type)]
        return factory_func(stg)
    except Exception as e:
        logger.error(f"create_trader_from_strategy: {e}")
        raise e
