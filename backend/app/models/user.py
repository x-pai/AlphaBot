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
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_reset_at = Column(DateTime(timezone=True), server_default=func.now())  # 上次重置使用次数的时间

    @property
    def is_unlimited(self):
        return self.points >= 1000

    @property
    def daily_limit(self):
        return 999999 if self.is_unlimited else 10

class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    used = Column(Boolean, default=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)

# 在模型定义之后添加关系
from app.models.stock import SavedStock
User.saved_stocks = relationship("SavedStock", back_populates="user", cascade="all, delete-orphan") 