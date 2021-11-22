import os

from btcturk_api.client import Client as RealApiClient
from dotenv import load_dotenv

load_dotenv()

apiKey = os.getenv("BTCTURK_PUBLIC_KEY")
apiSecret = os.getenv("BTCTURK_PRIVATE_KEY")

# singleton


def create_btcturk_api_client_real():
    return RealApiClient(api_key=apiKey, api_secret=apiSecret)
