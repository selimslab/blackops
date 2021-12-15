import os

from dotenv import load_dotenv

load_dotenv()

is_prod = os.getenv("PROD", "true").lower() in ("true", "1", "t")

if is_prod:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_PROD", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_PROD", "")
else:
    apiKey = os.getenv("BTCTURK_PUBLIC_KEY_TEST", "")
    apiSecret = os.getenv("BTCTURK_PRIVATE_KEY_TEST", "")
