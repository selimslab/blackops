import asyncio
from dataclasses import dataclass
from typing import List
import src.pubsub.pub as pub
from src.robots.context import robot_context
import simplejson as json  # type: ignore
from src.periodic import periodic
from src.monitoring import logger

@dataclass
class StatsStation:
    broadcasting = False

    async def broadcast_stats_periodically(self, period):
        if not self.broadcasting:
            self.broadcasting = True
            task = asyncio.create_task(periodic(self.broadcast_stats, period))
            
    async def broadcast_stats(self) -> None:
        stats = {}
        for robotrun in robot_context.robots.values():

            stat_dict = robotrun.robot.create_stats_message()

            stats[robotrun.sha] = stat_dict

        if stats:
            stats = json.dumps(stats, default=str)
            pub.publish_stats(message=stats)


robot_stats = StatsStation()