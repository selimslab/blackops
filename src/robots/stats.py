import asyncio
from dataclasses import dataclass
from typing import List
import src.pubsub.pub as pub
from src.robots.context import robot_context
import simplejson as json  # type: ignore
from src.periodic import periodic


@dataclass
class StatsStation:
    broadcasting = asyncio.Lock()

    async def broadcast_stats_periodically(self):
        async with self.broadcasting:
            task = asyncio.create_task(periodic(self.broadcast_stats, 1))
            await task

    async def broadcast_stats(self) -> None:
        stats = []
        for robotrun in robot_context.robots.values():

            stat_dict = robotrun.robot.create_stats_message()

            stat = json.dumps(stat_dict, default=str)

            stats.append(stat)

        if stats:
            pub.publish_stats(message=stats)


robot_stats = StatsStation()