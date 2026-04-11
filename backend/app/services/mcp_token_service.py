from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import McpToken, User


class McpTokenService:
    """MCP 访问令牌服务。"""

    TOKEN_PREFIX = "abmcp"

    @classmethod
    def _hash_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def generate_raw_token(cls) -> str:
        return f"{cls.TOKEN_PREFIX}_{secrets.token_urlsafe(32)}"

    @classmethod
    def create_token(
        cls,
        db: Session,
        user: User,
        name: str,
        expires_at: Optional[datetime] = None,
    ) -> tuple[McpToken, str]:
        token_name = (name or "").strip()
        if not token_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token name is required",
            )

        raw_token = cls.generate_raw_token()
        db_token = McpToken(
            user_id=user.id,
            name=token_name,
            token_prefix=raw_token[:12],
            token_hash=cls._hash_token(raw_token),
            expires_at=expires_at,
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        return db_token, raw_token

    @classmethod
    def list_tokens_for_user(cls, db: Session, user_id: int) -> list[McpToken]:
        return (
            db.query(McpToken)
            .filter(McpToken.user_id == user_id)
            .order_by(McpToken.created_at.desc(), McpToken.id.desc())
            .all()
        )

    @classmethod
    def list_all_tokens(cls, db: Session) -> list[McpToken]:
        return db.query(McpToken).order_by(McpToken.created_at.desc(), McpToken.id.desc()).all()

    @classmethod
    def revoke_token(
        cls,
        db: Session,
        token_id: int,
        current_user: User,
        allow_admin: bool = False,
    ) -> bool:
        query = db.query(McpToken).filter(McpToken.id == token_id)
        if not allow_admin or not current_user.is_admin:
            query = query.filter(McpToken.user_id == current_user.id)
        token = query.first()
        if not token:
            return False
        token.is_active = False
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @classmethod
    def authenticate_token(cls, db: Session, raw_token: str) -> McpToken:
        token = (
            db.query(McpToken)
            .filter(
                McpToken.token_hash == cls._hash_token(raw_token),
                McpToken.is_active.is_(True),
            )
            .first()
        )
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MCP token",
            )
        if token.expires_at and token.expires_at.replace(tzinfo=None) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MCP token expired",
            )
        if not token.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found for MCP token",
            )
        return token

    @classmethod
    def touch_token(cls, db: Session, token: McpToken, client_ip: Optional[str] = None) -> None:
        token.last_used_at = datetime.now(timezone.utc)
        token.last_used_ip = client_ip
        db.commit()
