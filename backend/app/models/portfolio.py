from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Position(Base):
    """
    用户持仓表

    对应 docs/README.md 中的 position：
    user_id, stock_id, symbol, quantity, cost_price, currency, source(manual/import/broker)
    """

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True, index=True)

    # 冗余 symbol，兼容未入库股票或快速查询
    symbol = Column(String(32), nullable=False, index=True)

    quantity = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=True)

    # 持仓来源：手工录入、导入、券商同步
    source = Column(String(20), nullable=False, default="manual")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="positions")
    stock = relationship("Stock", back_populates="positions")


class TradeLog(Base):
    """
    交易流水表

    对应 docs/README.md 中的 trade_log：
    user_id, stock_id, symbol, side(buy/sell),
    quantity, price, amount, fee, trade_time, source
    """

    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True, index=True)

    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # "buy" | "sell"

    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, nullable=True, default=0.0)

    trade_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source = Column(String(20), nullable=False, default="manual")

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trade_logs")
    stock = relationship("Stock", back_populates="trade_logs")

