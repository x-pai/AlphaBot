from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import asyncio
import time
from datetime import datetime, timedelta, timezone

from app.api.api import api_router
from app.core.config import settings
from app.db.session import engine, Base
from app.services.scheduler_service import SchedulerService
from app.services.telegram_poller import run_telegram_poller
from app.services.worldcup_service import WorldCupService
from app.core.mcp_host import McpHostRegistry
from app.middleware import RateLimitMiddleware, start_cleanup_task, stop_cleanup_task
from app.middleware.logging import logging_middleware

# 导入所有模型以确保它们被正确注册
from app.models.user import User, InviteCode
from app.models.stock import Stock, StockPrice, SavedStock
from app.models.conversation import Conversation
from app.models.portfolio import Position, TradeLog
from app.models.alert import AlertRule, AlertTrigger
from app.models.account import AccountConnection, AccountPosition, AccountTrade

# 初始化数据库
from app.db.init_db import init_database
init_database()


def next_run_at_shanghai(hour: int, minute: int = 0) -> float:
    shanghai_tz = timezone(timedelta(hours=8))
    now = datetime.now(shanghai_tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.timestamp()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = SchedulerService()
    await scheduler.start()

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

    await scheduler.add_task(
        WorldCupService.run_daily_refresh,
        interval=24 * 60 * 60,
        next_run=next_run_at_shanghai(11, 0),
        description="worldcup_daily_refresh",
        task_id="worldcup_daily_refresh",
    )

    await scheduler.add_task(
        WorldCupService.run_prekick_sync,
        interval=5 * 60,
        next_run=time.time() + 15,
        description="worldcup_prekick_sync",
        task_id="worldcup_prekick_sync",
    )

    asyncio.create_task(run_telegram_poller())

    try:
        McpHostRegistry.load_from_file()
        await McpHostRegistry.discover_tools()
    except Exception:
        pass

    await start_cleanup_task()

    try:
        yield
    finally:
        await scheduler.stop()
        await stop_cleanup_task()


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
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

if __name__ == "__main__":
    # 获取端口，默认为 8000
    port = int(os.environ.get("PORT", 8000))
    
    # 启动服务器
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 
