import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Coroutine, Dict, Optional
from src.monitoring import logger
import src.pubsub.pub as pub


@dataclass
class Station:
    pubsub_channel: str
    log_channel: str
    listeners: int = 0
    aiotask: Optional[asyncio.Task] = None


@dataclass
class Radio:
    stations: Dict[str, Station] = field(default_factory=dict)

    async def start_station(self, station: Station):
        if not station.aiotask:
            raise Exception(f"no aiotask set for station")
        try:
            await station.aiotask
        except asyncio.CancelledError as e:
            msg = f"station {station.pubsub_channel} cancelled: {e}"
            pub.publish_error(channel=station.log_channel, message=msg)
            del self.stations[station.pubsub_channel]
        except Exception as e:
            msg = f"restarting station {station.pubsub_channel}: {e}"
            pub.publish_error(channel=station.log_channel, message=msg)
            logger.error(msg)
            await self.start_station(station)

    def add_listener(self, pubsub_channel: str):
        if pubsub_channel in self.stations:
            self.stations[pubsub_channel].listeners += 1

    def drop_listener(self, pubsub_channel: str):
        station = self.stations.get(pubsub_channel)
        if station:
            self.stations[station.pubsub_channel].listeners -= 1
            self.stop_station_if_no_listeners(station)

    def stop_station_if_no_listeners(self, station: Station):
        if station.listeners == 0 and station.aiotask:
            station.aiotask.cancel()


radio = Radio()
