from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User


class UsageService:
    """统一处理用户日额度与 MCP 日额度。"""

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.utcnow()

    @classmethod
    def _reset_general_usage_if_needed(cls, user: User, db: Session) -> None:
        now = cls._utcnow()
        last_reset = (user.last_reset_at or now).replace(tzinfo=None)
        if now.date() > last_reset.date():
            user.daily_usage_count = 0
            user.last_reset_at = now
            db.commit()
            db.refresh(user)

    @classmethod
    def _reset_mcp_usage_if_needed(cls, user: User, db: Session) -> None:
        now = cls._utcnow()
        last_reset = (user.mcp_last_reset_at or user.last_reset_at or now).replace(tzinfo=None)
        if now.date() > last_reset.date():
            user.mcp_daily_usage_count = 0
            user.mcp_last_reset_at = now
            db.commit()
            db.refresh(user)

    @classmethod
    def check_general_usage(cls, user: User, db: Session) -> bool:
        cls._reset_general_usage_if_needed(user, db)
        if user.is_unlimited:
            return True
        return user.daily_usage_count < user.daily_limit

    @classmethod
    def consume_general_usage(cls, user: User, db: Session) -> None:
        cls._reset_general_usage_if_needed(user, db)
        if user.is_unlimited:
            return
        user.daily_usage_count += 1
        db.commit()
        db.refresh(user)

    @classmethod
    def require_general_usage(cls, user: User, db: Session) -> None:
        if not cls.check_general_usage(user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily usage limit exceeded",
            )
        cls.consume_general_usage(user, db)

    @classmethod
    def check_mcp_usage(cls, user: User, db: Session) -> bool:
        cls._reset_mcp_usage_if_needed(user, db)
        if not user.can_use_mcp:
            return False
        if user.is_unlimited:
            return True
        return user.mcp_daily_usage_count < user.mcp_daily_limit

    @classmethod
    def require_mcp_usage(cls, user: User, db: Session) -> None:
        cls._reset_mcp_usage_if_needed(user, db)
        if not user.can_use_mcp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MCP requires at least 200 points",
            )
        if user.is_unlimited:
            return
        if user.mcp_daily_usage_count >= user.mcp_daily_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MCP daily usage limit exceeded",
            )
        user.mcp_daily_usage_count += 1
        db.commit()
        db.refresh(user)
