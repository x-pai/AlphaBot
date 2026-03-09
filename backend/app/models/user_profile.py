"""
Phase 6 T6.5: 用户投资画像与目标 — 目标金额、定投间隔、下次定投日等。
"""

from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.session import Base


class UserProfile(Base):
    """用户投资画像：目标、定投、风控偏好等。"""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # 目标与定投（T6.5）
    target_amount = Column(Float, nullable=True)  # 目标总资产（元）
    dca_interval_days = Column(Integer, nullable=True)  # 定投间隔天数，如 7 表示每周
    next_dca_date = Column(Date, nullable=True)  # 下次建议定投日

    # 风控偏好（T6.4 可选）
    max_single_stock_pct = Column(Float, nullable=True)  # 单股仓位上限，如 0.2 表示 20%
    max_daily_loss_pct = Column(Float, nullable=True)  # 单日亏损提醒阈值，如 -5 表示跌超 5%
    max_sector_pct = Column(Float, nullable=True)  # 单行业仓位上限

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
