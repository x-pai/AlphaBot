from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class AccountConnection(Base):
    """统一账户连接：同花顺、QMT 等外部账户都作为 provider 接入。"""

    __tablename__ = "account_connections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    cash_balance = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="CNY")
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="account_connections")
    positions = relationship(
        "AccountPosition", back_populates="account", cascade="all, delete-orphan"
    )
    trades = relationship(
        "AccountTrade", back_populates="account", cascade="all, delete-orphan"
    )


class AccountPosition(Base):
    """统一持仓表。"""

    __tablename__ = "account_positions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("account_connections.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=True)
    source = Column(String(20), nullable=False, default="broker")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("AccountConnection", back_populates="positions")
    user = relationship("User", back_populates="account_positions")
    stock = relationship("Stock")


class AccountTrade(Base):
    """统一交易流水表。"""

    __tablename__ = "account_trades"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("account_connections.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, nullable=True, default=0.0)
    trade_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source = Column(String(20), nullable=False, default="broker")
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("AccountConnection", back_populates="trades")
    user = relationship("User", back_populates="account_trades")
    stock = relationship("Stock")
