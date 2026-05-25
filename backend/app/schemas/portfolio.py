from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

class TradeBase(BaseModel):
    symbol: str
    side: str  # "buy" / "sell"
    quantity: float
    price: float
    fee: float = 0.0
    source: str = "broker"
    trade_time: Optional[datetime] = None
    provider: Optional[str] = None
    account_id: Optional[int] = None


class TradeOut(TradeBase):
    id: int
    user_id: int
    stock_id: Optional[int] = None
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderBase(BaseModel):
    symbol: str
    side: str  # "buy" / "sell"
    quantity: float
    price: Optional[float] = None
    order_type: str = "limit"
    provider: Optional[str] = None
    account_id: Optional[int] = None


class OrderIn(OrderBase):
    pass


class OrderCancelIn(BaseModel):
    order_id: Optional[str] = None
    cancel_all: bool = False
    provider: Optional[str] = None
    account_id: Optional[int] = None


class OrderOut(OrderBase):
    id: Optional[int] = None
    user_id: int
    order_id: Optional[str] = None
    name: Optional[str] = None
    filled_quantity: float = 0.0
    status: str
    order_time: Optional[datetime] = None
    source: str = "broker"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
