from enum import Enum
import pydantic 
from pydantic import BaseModel,Field
from datetime import datetime
from typing import Optional


class StrategyType(str, Enum):
    SLIDING_WINDOW = "sliding_window"


class StrategyInputBase(BaseModel):
    type: str

    def is_valid(self):
        raise NotImplementedError


class StrategyConfigBase(BaseModel):
    input: StrategyInputBase
    type: StrategyType = StrategyType.SLIDING_WINDOW
    sha: str = ""
    created_at: str = Field(default_factory=lambda: str(datetime.now().isoformat()))

