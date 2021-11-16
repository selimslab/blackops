import os

from btcturk_api.client import Client
from dotenv import load_dotenv

load_dotenv()

apiKey = os.getenv("BTCTURK_PUBLIC_KEY")
apiSecret = os.getenv("BTCTURK_PRIVATE_KEY")

# singleton 
btcturk_client = Client(api_key = apiKey, api_secret = apiSecret)


     
