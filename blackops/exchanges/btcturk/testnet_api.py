from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from beartype import beartype


@beartype
@dataclass
class TestnetApi:
    balances: Dict[str, Decimal] = field(default_factory=dict)

    def set_balance(self, symbol: str, val: Decimal):
        self.balances[symbol] = val

    def get_balance(self, symbol: str) -> Optional[Decimal]:
        return self.balances.get(symbol, Decimal(0))

    def get_account_balance(self, assets: List[str]) -> List[Decimal]:
        return [self.balances[symbol] for symbol in assets]


btcturk_api_client_testnet = TestnetApi()
