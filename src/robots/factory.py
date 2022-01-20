from dataclasses import dataclass

import src.pubsub.log_pub as log_pub
from src.monitoring import logger
from src.robots.sliding.factory import sliding_window_factory
from src.stgs import StrategyConfig, StrategyType

from .sliding.main import LeaderFollowerTrader

Robot = LeaderFollowerTrader  # union type


@dataclass
class RobotFactory:

    FACTORIES = {
        StrategyType.SLIDING_WINDOW: sliding_window_factory,
    }

    def create_robot(
        self,
        stg: StrategyConfig,
    ) -> Robot:
        try:
            stg.is_valid()
            factory_func = self.FACTORIES[StrategyType(stg.type)]
            return factory_func(stg)
        except Exception as e:
            msg = f"create_trader_from_strategy: {e}"
            logger.error(msg)
            log_pub.publish_error(msg)
            raise e


robot_factory = RobotFactory()
