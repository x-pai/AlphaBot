from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

from app.api.api import api_router
from app.core.config import settings
from app.db.session import engine, Base
from app.services.scheduler_service import SchedulerService
from app.middleware import RateLimitMiddleware, start_cleanup_task, stop_cleanup_task
from app.middleware.logging import logging_middleware

# 导入所有模型以确保它们被正确注册
from app.models.user import User, InviteCode
from app.models.stock import Stock, StockPrice, SavedStock
from app.models.conversation import Conversation
from app.models.portfolio import Position, TradeLog
from app.models.alert import AlertRule, AlertTrigger

# 初始化数据库
from app.db.init_db import init_database
init_database()

# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# 添加请求频率限制中间件
app.add_middleware(RateLimitMiddleware)

# 添加日志中间件
app.middleware("http")(logging_middleware)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 健康检查
@app.get("/health")
def health_check():
    return {"status": "ok"}

# 启动事件
@app.on_event("startup")
async def startup_event():
    # 启动调度器
    scheduler = SchedulerService()
    await scheduler.start()

    # 每 5 分钟评估一次预警规则（Phase 2）
    from app.db.session import SessionLocal
    from app.services.alert_service import AlertService

    async def run_alert_evaluation():
        db = SessionLocal()
        try:
            await AlertService.evaluate_all_rules(db)
        finally:
            db.close()

    await scheduler.add_task(
        run_alert_evaluation,
        interval=300,
        description="evaluate_all_alert_rules",
        task_id="alert_evaluate_all_rules",
    )
    
    # 启动请求频率限制中间件的清理任务
    await start_cleanup_task()

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    # 停止调度器
    scheduler = SchedulerService()
    await scheduler.stop()
    
    # 停止请求频率限制中间件的清理任务
    await stop_cleanup_task()

if __name__ == "__main__":
    # 获取端口，默认为 8000
    port = int(os.environ.get("PORT", 8000))
    
    # 启动服务器
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 