import decimal
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel

from src.monitoring import logger

load_dotenv()

decimal.getcontext().prec = 9


class SleepSeconds(BaseModel):

    clear_prices: float = 0.42
    clear_balance: float = 2.1

    rate_limit: float = 5

    read_wait: float = 0.17  # 300/min
    cancel_wait: float = 0.17  # 300/min
    sell_wait: float = 0.16
    buy_wait: float = 0.17

    update_balances: float = 0.72  # 90/min
    refresh_open_orders: float = 0.8  # try every 200ms, 6 robots 1.2 secs

    broadcast_stats: float = 1


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
