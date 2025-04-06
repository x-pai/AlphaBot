from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.user_service import UserService
from app.models.user import User
from app.api.routes.user import get_current_user
from app.core.config import settings

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

async def check_web_search_limit(
    current_user: User = Depends(get_current_user)
):
    """检查用户是否可以使用联网搜索功能
    
    要求:
    1. 系统启用了搜索API
    2. 用户至少拥有2000积分
    """
    # 检查是否启用搜索API
    if not settings.SEARCH_API_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search API is not enabled"
        )
    
    # 检查用户积分是否足够
    if current_user.points < 2000:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient points, 2000 points required for web search"
        )
    
    return current_user 