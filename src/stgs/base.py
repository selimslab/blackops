from datetime import datetime
from enum import Enum

import pydantic
from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    SLIDING_WINDOW = "sliding_window"


class StrategyInputBase(BaseModel):
    type: str

    def is_valid(self):
        raise NotImplementedError


class StrategyConfigBase(BaseModel):
    input: StrategyInputBase
    type: StrategyType
    sha: str = ""
