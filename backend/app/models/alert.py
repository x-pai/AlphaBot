"""
预警规则与触发记录

README: alert_rule(user_id, symbol, rule_type, params_json, enabled)
       alert_trigger(alert_rule_id, user_id, symbol, triggered_at, message, is_read)
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class AlertRule(Base):
    """用户预警规则"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    # price_change_pct | price_vs_ma | volume_spike
    rule_type = Column(String(32), nullable=False, index=True)
    params_json = Column(Text, nullable=True)  # JSON: {"threshold_pct": -5}, {"ma_period": 20, "above_below": "below"}, {"multiplier": 2}
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="alert_rules")
    triggers = relationship("AlertTrigger", back_populates="alert_rule", cascade="all, delete-orphan")


class AlertTrigger(Base):
    """预警触发记录（同一规则同一自然日只触发一次，见合规）"""

    __tablename__ = "alert_triggers"

    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)

    alert_rule = relationship("AlertRule", back_populates="triggers")
    user = relationship("User", back_populates="alert_triggers")
