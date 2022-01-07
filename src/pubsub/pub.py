from datetime import datetime

from src.pubsub.client import pusher_client
from src.monitoring import logger

from typing import Any
from enum import Enum

DEFAULT_CHANNEL = "f7299bf"

ERROR = "ERROR"
MESSAGE =  "MESSAGE"
STATS = "STATS"


def add_time(message):
    return {
        "message": message,
        "time": str(datetime.now().time()),
    }


def publish_error(message, channel: str=DEFAULT_CHANNEL):
    pusher_client.trigger(channel, ERROR, add_time(message))


def publish_message(message, channel: str=DEFAULT_CHANNEL):
    pusher_client.trigger(channel, MESSAGE, add_time(message))


def publish_stats(message, channel: str=DEFAULT_CHANNEL):
    pusher_client.trigger(channel, STATS, add_time(message))


if __name__ == "__main__":
    import json
    publish_stats(message=json.dumps({"dsd":"fsdfds"}))
