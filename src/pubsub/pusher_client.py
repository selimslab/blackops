import pusher

from src.monitoring import logger

try:
    pusher_client = pusher.Pusher(
        app_id="1301008",
        key="7b2411e6822e2f36b872",
        secret="5fd8d4400165c6ce64b2",
        cluster="eu",
        ssl=True,
    )
except Exception as e:
    logger.info(f"pusher: {e}")
