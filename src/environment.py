import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel

from src.monitoring import logger

load_dotenv()


class SleepSeconds(BaseModel):
    update_balances: float = 0.72
    cancel_all_open_orders: float = 1
    broadcast_stats: float = 1
    clear_prices: float = 0.36
    clear_balance: float = 1.6
    wait_between_orders: float = 0.18
    wait_between_orders_for_robots: float = 0.12
    rate_limit_seconds: float = 5


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
