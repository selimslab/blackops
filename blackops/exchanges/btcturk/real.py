from btcturk_api.client import Client as RealApiClient

from blackops.environment import apiKey, apiSecret

# singleton


def create_btcturk_api_client_real():
    return RealApiClient(api_key=apiKey, api_secret=apiSecret)
