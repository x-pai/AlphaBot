from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.user_service import UserService
from app.models.user import User
from app.api.routes.user import get_current_user

async def check_usage_limit(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查用户使用限制的依赖"""
    can_use = await UserService.check_user_usage(current_user, db)
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily usage limit exceeded"
        )
    await UserService.increment_usage(current_user, db)
    return current_user 