from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    points = Column(Integer, default=120)  # 初始积分120
    daily_usage_count = Column(Integer, default=0)  # 每日使用次数
    mcp_daily_usage_count = Column(Integer, default=0)  # MCP每日使用次数
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_reset_at = Column(DateTime(timezone=True), server_default=func.now())  # 上次重置使用次数的时间
    mcp_last_reset_at = Column(DateTime(timezone=True), server_default=func.now())  # 上次重置MCP使用次数的时间

    @property
    def is_unlimited(self):
        return self.points >= 1000

    @property
    def daily_limit(self):
        if self.is_unlimited:
            return 999999
        if self.points >= 300:
            return 50
        return 10

    @property
    def can_use_mcp(self):
        return self.points >= 200

    @property
    def mcp_daily_limit(self):
        if self.is_unlimited:
            return 999999
        if self.points >= 500:
            return 300
        if self.points >= 300:
            return 100
        return 50

class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    used = Column(Boolean, default=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)


class McpToken(Base):
    __tablename__ = "mcp_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    token_prefix = Column(String, nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)

# 在模型定义之后添加关系
from app.models.stock import SavedStock
from app.models.portfolio import Position, TradeLog
from app.models.alert import AlertRule, AlertTrigger

User.saved_stocks = relationship(
    "SavedStock", back_populates="user", cascade="all, delete-orphan"
)
User.positions = relationship(
    "Position", back_populates="user", cascade="all, delete-orphan"
)
User.trade_logs = relationship(
    "TradeLog", back_populates="user", cascade="all, delete-orphan"
)
User.alert_rules = relationship(
    "AlertRule", back_populates="user", cascade="all, delete-orphan"
)
User.alert_triggers = relationship(
    "AlertTrigger", back_populates="user", cascade="all, delete-orphan"
)
User.mcp_tokens = relationship(
    "McpToken", backref="user", cascade="all, delete-orphan"
)
