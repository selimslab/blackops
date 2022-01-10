import asyncio
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Coroutine, Dict, Optional, List

from src.robots.radio import radio, Radio, Station

from src.robots.watchers import watcher_factory

import src.pubsub.pub as pub
from src.stgs import StrategyConfig
from src.robots.watchers import BalanceWatcher, BookWatcher
from src.monitoring import logger
from src.periodic import periodic




@dataclass
class StationApi:
    radio: Radio = radio

    def create_balance_station_if_not_exists(
        self, config: StrategyConfig, balance_gen: BalanceWatcher
    ) -> Optional[Coroutine]:
        if balance_gen.pubsub_key in self.radio.stations:
            self.radio.add_listener(balance_gen.pubsub_key)
            return None
        else:
            balance_task = periodic(
                balance_gen.watch_balance, config.sleep_seconds.update_balances
            )
            station = Station(
                name="balance_station",
                pubsub_channel=balance_gen.pubsub_key,
                log_channel=pub.DEFAULT_CHANNEL,
                listeners=1,
                aiotask=asyncio.create_task(balance_task)
            )
            return self.radio.run_station_till_cancelled(station)
            
    def create_bridge_station_if_not_exists(
        self, stg: StrategyConfig, bridge_gen: BookWatcher
    ) -> Optional[Coroutine]:
        if bridge_gen.pubsub_key in self.radio.stations:
            self.radio.add_listener(bridge_gen.pubsub_key)
            return None
        else:
            station = Station(
                name="bridge_station",
                pubsub_channel=bridge_gen.pubsub_key,
                log_channel=pub.DEFAULT_CHANNEL,
                listeners=1,
                aiotask=asyncio.create_task(bridge_gen.watch_books()),
            )
            return self.radio.run_station_till_cancelled(station)

    def create_log_station_if_not_exists(self, task):
        if pub.DEFAULT_CHANNEL in self.radio.stations:
            return None 
        else:
            station = Station(
                name="stats_station",
                pubsub_channel=pub.DEFAULT_CHANNEL,
                log_channel=pub.DEFAULT_CHANNEL,
                listeners=1,
                aiotask=task,
            )
            return self.radio.run_station_till_cancelled(station)


station_api = StationApi()