"""
Phase 6 T6.3: 模拟交易 — 虚拟资金与模拟持仓，使用实盘行情。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class SimAccount(Base):
    """用户模拟账户：虚拟现金。"""

    __tablename__ = "sim_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    cash_balance = Column(Float, nullable=False, default=1_000_000.0)  # 初始 100 万
    currency = Column(String(10), nullable=True, default="CNY")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SimPosition(Base):
    """模拟持仓：与 Position 结构类似，独立表便于区分实盘。"""

    __tablename__ = "sim_positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
