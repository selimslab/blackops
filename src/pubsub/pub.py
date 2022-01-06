from datetime import datetime

from src.pubsub.client import pusher_client
from src.monitoring import logger


def add_time(message):
    return {
        "message": message,
        "time": str(datetime.now().time()),
    }


def publish_error(channel: str, message):
    try:
        pusher_client.trigger(channel, "error", add_time(message))
    except Exception as e:
        logger.info(f"{message} {e}")


def publish_message(channel: str, message):
    pusher_client.trigger(channel, "message", add_time(message))


def publish_stats(channel: str, message):
    pusher_client.trigger(channel, "stats", add_time(message))


if __name__ == "__main__":
    publish_error("test", "test")
