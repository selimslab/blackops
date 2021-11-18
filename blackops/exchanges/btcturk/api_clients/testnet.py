from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from beartype import beartype


@dataclass
class TestnetApi:
    balances: Dict[str, Decimal] = field(default_factory=dict)

    async def set_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] = val

    async def get_balance(self, symbol: str) -> Optional[Decimal]:
        return self.balances.get(symbol, Decimal(0))

    async def get_account_balance(self, assets: List[str]) -> List[dict]:
        return [{"balance": self.balances[symbol]} for symbol in assets]


def create_btcturk_api_client_testnet(balances: dict):
    btcturk_api_client_testnet = TestnetApi(balances)
    return btcturk_api_client_testnet
