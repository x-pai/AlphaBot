from fastapi import APIRouter
from app.api.routes import stocks, user, ai, tasks, reports
from app.api.routes import async_ai

api_router = APIRouter()

# 注册各个模块的路由
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(async_ai.router, prefix="/async/ai", tags=["async_ai"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"]) 