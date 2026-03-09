from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PositionBase(BaseModel):
    symbol: str
    quantity: float
    cost_price: float
    currency: Optional[str] = None
    source: str = "manual"


class PositionCreate(PositionBase):
    """创建/覆盖持仓（直接录入，不记交易流水）"""
    pass


class PositionOut(PositionBase):
    id: int
    user_id: int
    stock_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TradeBase(BaseModel):
    symbol: str
    side: str  # "buy" / "sell"
    quantity: float
    price: float
    fee: float = 0.0
    source: str = "manual"
    trade_time: Optional[datetime] = None


class TradeIn(TradeBase):
    pass


class TradeOut(TradeBase):
    id: int
    user_id: int
    stock_id: Optional[int] = None
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

