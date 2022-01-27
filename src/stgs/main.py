from src.stgs.sliding.config import LeaderFollowerConfig, LeaderFollowerInput

from .base import StrategyType

StrategyInput = LeaderFollowerInput

StrategyConfig = LeaderFollowerConfig

STRATEGY_INPUT_CLASS = {StrategyType.SLIDING_WINDOW: LeaderFollowerInput}

STRATEGY_CONFIG_CLASS = {StrategyType.SLIDING_WINDOW: LeaderFollowerConfig}
