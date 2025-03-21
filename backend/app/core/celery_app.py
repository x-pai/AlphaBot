from celery import Celery
from app.core.config import settings
import os

# 使用settings中的配置
celery_app = Celery(
    "ai_stock_assistant",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# 自动发现任务
celery_app.autodiscover_tasks(['app.tasks'])

# 导入任务模块确保任务被注册
import app.tasks.ai_tasks

# 配置Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=False,
    task_routes={
        "app.tasks.ai_tasks.*_task": {"queue": "ai_tasks"},
    },
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    # 增加连接重试相关设置
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
) 