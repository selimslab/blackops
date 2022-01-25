import decimal
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel

from src.monitoring import logger

load_dotenv()

decimal.getcontext().prec = 9


class SleepSeconds(BaseModel):

    clear_follower_prices: float = 0.6

    rate_limit: float = 5

    read_wait: float = 0.16  # 300/min
    cancel_wait: float = 0.16  # 300/min

    update_balances: float = 0.72  # 90/min
    poll_balance_update: float = update_balances / 18

    refresh_open_orders: float = 0.3

    broadcast_stats: float = 0.8

    wait_before_cancel: float = 0.12
    wait_after_failed_order: float = 0.15

    poll_for_lock: float = 0.05


sleep_seconds = SleepSeconds()


@dataclass
class Environment:
    pass


debug = os.getenv("DEBUG", "true").lower() in ("true", "1", "t")

logger.info(f"Debug mode: {debug}")

if debug:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_TEST", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_TEST", "")
else:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_PROD", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_PROD", "")


def test_debug():
    print(debug)
