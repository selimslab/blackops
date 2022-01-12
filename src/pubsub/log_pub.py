from datetime import datetime

from src.monitoring import logger
from src.pubsub.pusher_client import pusher_client

DEFAULT_CHANNEL = "f7299bf"

ERROR = "ERROR"
MESSAGE = "MESSAGE"
STATS = "STATS"


def add_time(message):
    return {
        "message": message,
        "time": str(datetime.now().time()),
    }


def publish_error(message, channel: str = DEFAULT_CHANNEL):
    try:
        pusher_client.trigger(channel, ERROR, add_time(message))
    except Exception as e:
        pass


def publish_message(message, channel: str = DEFAULT_CHANNEL):
    try:
        pusher_client.trigger(channel, MESSAGE, add_time(message))
    except Exception as e:
        pass


def publish_stats(message, channel: str = DEFAULT_CHANNEL):
    try:
        pusher_client.trigger(channel, STATS, add_time(message))
    except Exception as e:
        pass


if __name__ == "__main__":
    import json

    publish_stats(message=json.dumps({"dsd": "fsdfds"}))
