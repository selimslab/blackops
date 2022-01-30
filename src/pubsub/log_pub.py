from datetime import datetime

from src.environment import LOG_RADIO
from src.monitoring import logger
from src.pubsub.pusher_client import pusher_client

DEFAULT_CHANNEL = LOG_RADIO

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
        logger.error(e)


def publish_message(message, channel: str = DEFAULT_CHANNEL):
    try:
        pusher_client.trigger(channel, MESSAGE, add_time(message))
    except Exception as e:
        logger.error(e)


def publish_stats(message, channel: str = DEFAULT_CHANNEL):
    try:
        pusher_client.trigger(channel, STATS, add_time(message))
    except Exception as e:
        logger.error(e)


if __name__ == "__main__":
    import json

    publish_stats(message=json.dumps({"dsd": "fsdfds"}))
