import blackops.domain.symbols as symbols
from blackops.clients.btcturk.main import btcturk_client


def test_client():
    balance = btcturk_client.get_account_balance(assets=[symbols.TRY, symbols.BTC])
    open_orders = btcturk_client.get_open_orders()

    print(open_orders)

if __name__ == "__main__":
    test_client()


