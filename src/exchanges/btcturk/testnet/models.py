from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.domain import (
    Asset,
    AssetPair,
    AssetPairSymbol,
    AssetSymbol,
    OrderId,
    OrderType,
)


class AccountBalanceResponse(BaseModel):
    success: bool
    data: Optional[List[Asset]] = None
    message: Optional[str] = None


class OrderData(BaseModel):
    id: OrderId
    pairSymbol: str
    type: OrderType
    price: str
    stopPrice: str
    quantity: str
    leftAmount: str
    datetime: int


class SubmitOrderResponse(BaseModel):
    success: bool
    data: Optional[OrderData] = None
    message: Optional[str] = None


class OpenOrdersData(BaseModel):
    bids: List[OrderData] = Field(default_factory=list)
    asks: List[OrderData] = Field(default_factory=list)


class OpenOrdersResponse(BaseModel):
    success: bool
    data: OpenOrdersData
    message: Optional[str] = None


class Account(BaseModel):
    assets: Dict[AssetSymbol, Asset] = Field(default_factory=dict)
    open_orders: Dict[AssetPairSymbol, OpenOrdersData] = Field(default_factory=dict)
    all_orders: List[OrderData] = Field(default_factory=list)
