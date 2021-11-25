import os

from dotenv import load_dotenv

load_dotenv()

apiKey = os.getenv("BTCTURK_PUBLIC_KEY")
apiSecret = os.getenv("BTCTURK_PRIVATE_KEY")

is_prod = os.getenv("PROD", "False").lower() in ("true", "1", "t")
