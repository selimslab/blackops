import asyncio
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Coroutine, Dict, List, Optional

import src.pubsub.log_pub as log_pub
from src.monitoring import logger
from src.pubsub.pubs import PublisherBase


@dataclass
class Station:
    pubsub_channel: str
    log_channel: str
    coro: Coroutine
    listeners: int = 0
    aiotask: Optional[asyncio.Task] = None


@dataclass
class Radio:
    stations: Dict[str, Station] = field(default_factory=dict)

    @asynccontextmanager
    async def station_context(self, station: Station):
        try:
            if not station.aiotask:
                station.aiotask = asyncio.create_task(station.coro)
            self.stations[station.pubsub_channel] = station
            yield station.aiotask
        finally:
            self.clean_station(station)

    def clean_station(self, station: Station):
        if station.aiotask:
            station.aiotask.cancel()
        del self.stations[station.pubsub_channel]

    async def run_until_cancelled(self, station: Station):
        while True:
            async with self.station_context(station) as task:
                try:
                    await task
                except asyncio.CancelledError as e:
                    msg = f"station {station.pubsub_channel} cancelled: {e}"
                    log_pub.publish_error(message=msg)
                    break
                except Exception as e:
                    msg = f"restarting station {station.pubsub_channel}: {e} \n {traceback.format_exc()}"
                    log_pub.publish_error(message=msg)
                    logger.error(msg)
                    continue

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

    def create_station_if_not_exists(self, pubsub_key: str, coro: Coroutine):
        if pubsub_key in self.stations:
            self.add_listener(pubsub_key)
            return None
        else:
            station = Station(
                pubsub_channel=pubsub_key,
                log_channel=log_pub.DEFAULT_CHANNEL,
                listeners=1,
                coro=coro,
            )
            return self.run_until_cancelled(station)

    async def start_station_if_not_running(self, station: Station):
        await self.run_until_cancelled(station)

    def get_stations(self) -> List[Station]:
        return list(self.stations.values())


radio = Radio()
