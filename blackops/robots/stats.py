from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import blackops.pubsub.pub as pub
from blackops.environment import debug
from blackops.robots.base import RobotBase
from blackops.util.logger import logger


@dataclass
class RobotStats:
    task_start_time: datetime
    pnl: Decimal = Decimal("0")
    max_pnl: Decimal = Decimal("0")

    def runtime_seconds(self):
        return (datetime.now() - self.task_start_time).total_seconds()
