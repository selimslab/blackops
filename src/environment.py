import decimal
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel

from src.monitoring import logger

load_dotenv()

decimal.getcontext().prec = 9


class SleepSeconds(BaseModel):

    rate_limit: float = 5

    read_wait: float = 0.16  # 300/min
    cancel_wait: float = 0.16  # 300/min

    update_balances: float = 0.72  # 90/min

    refresh_open_orders: float = 0.3

    broadcast_stats: float = 1

    wait_before_cancel: float = 0.12
    wait_after_deliver_sell: float = 0.12
    wait_after_deliver_buy: float = 0.24

    wait_after_failed_order: float = 0.24

    poll_for_lock: float = 0.07


sleep_seconds = SleepSeconds()


@dataclass
class Environment:
    pass


debug = os.getenv("DEBUG", "true").lower() in ("true", "1", "t")

logger.info(f"Debug mode: {debug}")

if debug:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_TEST", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_TEST", "")
    LOG_RADIO = "0"
else:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_PROD", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_PROD", "")
    LOG_RADIO = "LOG_RADIO"


def test_debug():
    print(debug)
