from datetime import datetime

from blackops.pubsub.client import pusher_client

stats = "stats"

message = "message"

error = "error"

params = "params"

order = "order"


def add_time(message):
    return {
        "message": message,
        "time": str(datetime.now().time()),
    }


def publish_params(chaannel: str, message):
    pusher_client.trigger(chaannel, params, add_time(message))


def publish_order(chaannel: str, message):
    pusher_client.trigger(chaannel, order, add_time(message))


def publish_error(chaannel: str, message):
    pusher_client.trigger(chaannel, error, add_time(message))


def publish_message(chaannel: str, message):
    pusher_client.trigger(chaannel, message, add_time(message))


def publish_stats(chaannel: str, message):
    pusher_client.trigger(chaannel, stats, add_time(message))


if __name__ == "__main__":
    publish_error("test", "test")
