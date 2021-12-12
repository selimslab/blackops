from btcturk_api.client import Client as RealApiClient

from blackops.environment import apiKey, apiSecret

# singleton


def create_btcturk_api_client_real():
    return RealApiClient(api_key=apiKey, api_secret=apiSecret)


if __name__ == "__main__":
    # real_api = create_btcturk_api_client_real()

    # print(real_api.get_account_balance())
    pass
