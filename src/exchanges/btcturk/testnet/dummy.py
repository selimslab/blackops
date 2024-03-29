import random
import time
from dataclasses import dataclass, field
from decimal import Decimal

from src.domain import Asset, AssetPair
from src.exchanges.btcturk.testnet.models import (
    Account,
    AccountBalanceResponse,
    OpenOrdersData,
    OpenOrdersResponse,
    OrderData,
    OrderType,
    SubmitOrderResponse,
)
from src.monitoring import logger


@dataclass
class BtcturkDummy:
    account: Account = field(default_factory=Account)

    async def mock_account_balance(self) -> AccountBalanceResponse:
        return AccountBalanceResponse(
            success=True, data=list(self.account.assets.values())
        )

    def _init_asset_if_not_exists(self, symbol: str) -> None:
        if symbol not in self.account.assets:
            self.account.assets[symbol] = Asset(symbol=symbol)

    def _init_pair_if_not_exists(self, pair_symbol: str) -> None:
        if pair_symbol not in self.account.open_orders:
            self.account.open_orders[pair_symbol] = OpenOrdersData()

    def add_balance(self, asset: Asset, val: Decimal):
        self._init_asset_if_not_exists(asset.symbol)

        self.account.assets[asset.symbol].free += val

    def subtract_balance(self, asset: Asset, val: Decimal):
        self._init_asset_if_not_exists(asset.symbol)

        if self.account.assets[asset.symbol].free < val:
            raise Exception(
                f"Insufficient funds: have {self.account.assets[asset.symbol].free} {asset.symbol} but need {val}"
            )

        self.account.assets[asset.symbol].free -= val

    async def mock_get_open_orders(self, pair: AssetPair) -> OpenOrdersResponse:
        self._init_pair_if_not_exists(pair.symbol)

        return OpenOrdersResponse(
            success=True, data=self.account.open_orders[pair.symbol]
        )

    async def buy(self, pair: AssetPair, order: OrderData) -> SubmitOrderResponse:

        quote_balance = self.account.assets[pair.quote.symbol].free

        cost = Decimal(order.quantity) * Decimal(order.price)

        if quote_balance < cost:
            return SubmitOrderResponse(
                success=False,
                message=f"Insufficient funds: have {quote_balance} {pair.quote.symbol} but need {cost}",
            )

        self.account.open_orders[pair.symbol].bids.append(order)

        try:
            self.subtract_balance(pair.quote, cost)
            self.add_balance(pair.base, Decimal(order.quantity))
        except Exception as e:
            return SubmitOrderResponse(success=False, message=e)

        order.leftAmount = "0"
        res = SubmitOrderResponse(success=True, data=order)

        self.account.open_orders[pair.symbol].bids.pop()
        self.account.all_orders.append(order)

        return res

    async def sell(self, pair: AssetPair, order: OrderData) -> SubmitOrderResponse:

        base_balance = self.account.assets[pair.base.symbol].free

        if base_balance < Decimal(order.quantity):
            return SubmitOrderResponse(
                success=False,
                message=f"Insufficient funds: have {base_balance} {pair.base.symbol} but need {order.quantity}",
            )

        self.account.open_orders[pair.symbol].asks.append(order)

        gain = Decimal(order.quantity) * Decimal(order.price)
        try:
            self.subtract_balance(pair.base, Decimal(order.quantity))
            self.add_balance(pair.quote, gain)
        except Exception as e:
            return SubmitOrderResponse(success=False, message=e)

        order.leftAmount = "0"
        res = SubmitOrderResponse(success=True, data=order)

        self.account.open_orders[pair.symbol].asks.pop()
        self.account.all_orders.append(order)

        return res

    async def mock_submit_limit_order(
        self, pair: AssetPair, order_type: str, price: float, quantity: float
    ) -> SubmitOrderResponse:

        self._init_asset_if_not_exists(pair.base.symbol)
        self._init_asset_if_not_exists(pair.quote.symbol)
        self._init_pair_if_not_exists(pair.symbol)

        order = OrderData(
            id=random.randint(1, 1000000),
            datetime=int(time.time() * 1000),
            price=str(price),
            quantity=str(quantity),
            type=order_type,
            pairSymbol=pair.symbol,
            leftAmount=str(quantity),
            stopPrice=str(price),
        )
        if order_type == "buy":
            return await self.buy(pair, order)
        elif order_type == "sell":
            return await self.sell(pair, order)
        else:
            return SubmitOrderResponse(
                success=False, data=None, message="Invalid order type"
            )
