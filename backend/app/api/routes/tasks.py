from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.session import get_db
from app.services.scheduler_service import SchedulerService
from app.schemas.task import TaskCreate, TaskUpdate, TaskInfo
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit
from app.utils.stock_utils import update_stock_data_with_db
from app.services.automation_service import AutomationService
from app.api.routes.user import get_current_admin
from app.models.user import User
from app.core.config import settings
from app.services.channel_service import validate_notification

router = APIRouter()


def _compute_next_run(daily_time: Optional[str], timezone_name: Optional[str], fallback_interval: int) -> Optional[float]:
    if not daily_time:
        return None
    try:
        hour_text, minute_text = daily_time.split(":", 1)
        tz = ZoneInfo(timezone_name or settings.APP_TIMEZONE)
        now = datetime.now(tz)
        next_run_dt = now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
        if next_run_dt <= now:
            next_run_dt += timedelta(days=1)
        return next_run_dt.timestamp()
    except Exception:
        return None

@router.get("", response_model=dict)
async def get_all_tasks(
    _current_user: User = Depends(get_current_admin),
):
    """获取所有定时任务"""
    scheduler = SchedulerService()
    tasks = await scheduler.get_all_tasks()
    return api_response(data=tasks)

@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: str,
    _current_user: User = Depends(get_current_admin),
):
    """获取特定定时任务"""
    scheduler = SchedulerService()
    task = await scheduler.get_task(task_id)
    if not task:
        return api_response(success=False, error="任务不存在")
    return api_response(data=task)

@router.post("", response_model=dict)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    _: None = Depends(check_usage_limit)
):
    """创建定时任务"""
    scheduler = SchedulerService()
    
    if task.task_type == "update_stock_data":
        params = dict(task.params or {})
        if task.symbol:
            params["symbol"] = task.symbol
        task_id = await scheduler.add_task(
            func=update_stock_data_with_db,
            args=[task.symbol] if task.symbol else [],
            interval=task.interval,
            description=task.description or f"更新股票数据: {task.symbol if task.symbol else '所有'}",
            is_enabled=task.is_enabled,
            task_type=task.task_type,
            params=params,
        )
    elif task.task_type == "skill_publish_job":
        params = dict(task.params or {})
        params["user_id"] = current_user.id
        try:
            params["notify_channel"] = validate_notification(db, current_user.id, params.get("notify_channel"))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        next_run = _compute_next_run(
            params.get("daily_time"),
            params.get("timezone"),
            task.interval,
        )
        task_id = await scheduler.add_task(
            func=AutomationService.execute_skill_publish_job,
            kwargs={
                "task_id": "",
                "params": params,
            },
            interval=task.interval,
            next_run=next_run,
            description=task.description or "Skill 自动化发布任务",
            is_enabled=task.is_enabled,
            task_type=task.task_type,
            params=params,
        )
        # 回填真实 task_id 供执行函数使用
        task_obj = scheduler._tasks.get(task_id)
        if task_obj:
            task_obj.kwargs["task_id"] = task_id
    else:
        return api_response(success=False, error="不支持的任务类型")
    
    if not task_id:
        return api_response(success=False, error="创建任务失败")
    
    # 获取创建的任务信息
    new_task = await scheduler.get_task(task_id)
    return api_response(data=new_task)

@router.put("/{task_id}", response_model=dict)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    _: None = Depends(check_usage_limit)
):
    """更新定时任务"""
    scheduler = SchedulerService()
    
    # 检查任务是否存在
    existing_task = await scheduler.get_task(task_id)
    if not existing_task:
        return api_response(success=False, error="任务不存在")

    merged_params = task_update.params
    if existing_task.get("task_type") == "skill_publish_job":
        merged_params = dict(existing_task.get("params") or {})
        if task_update.params:
            merged_params.update(task_update.params)
        merged_params["user_id"] = current_user.id
        try:
            merged_params["notify_channel"] = validate_notification(db, current_user.id, merged_params.get("notify_channel"))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    next_run = None
    if merged_params and isinstance(merged_params, dict):
        next_run = _compute_next_run(
            merged_params.get("daily_time"),
            merged_params.get("timezone"),
            task_update.interval or existing_task.get("interval") or 86400,
        )

    # 更新任务
    success = await scheduler.update_task(
        task_id=task_id,
        interval=task_update.interval,
        next_run=next_run,
        is_enabled=task_update.is_enabled,
        description=task_update.description,
        params=merged_params,
    )
    
    if not success:
        return api_response(success=False, error="更新任务失败")
    
    # 获取更新后的任务信息
    updated_task = await scheduler.get_task(task_id)
    return api_response(data=updated_task)

@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: str,
    _current_user: User = Depends(get_current_admin),
):
    """删除定时任务"""
    scheduler = SchedulerService()
    
    # 检查任务是否存在
    if not await scheduler.get_task(task_id):
        return api_response(success=False, error="任务不存在")
    
    # 删除任务
    success = await scheduler.remove_task(task_id)
    
    if not success:
        return api_response(success=False, error="删除任务失败")
    
    return api_response(data={"message": "任务已删除"})

@router.post("/{task_id}/run", response_model=dict)
async def run_task_now(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin),
    _: None = Depends(check_usage_limit)
):
    """立即运行定时任务"""
    scheduler = SchedulerService()
    
    # 检查任务是否存在
    task = await scheduler.get_task(task_id)
    if not task:
        return api_response(success=False, error="任务不存在")
    
    if task.get("task_type") == "skill_publish_job":
        params = dict(task.get("params") or {})
        if not params.get("user_id"):
            params["user_id"] = current_user.id
            await scheduler.update_task(task_id=task_id, params=params)
        success = await scheduler.run_task_now(task_id)
        updated_task = await scheduler.get_task(task_id)
        if not success:
            return api_response(success=False, error=updated_task.get("error") if updated_task else "任务执行失败")
        return api_response(data=updated_task)

    # 在后台运行任务
    background_tasks.add_task(scheduler.run_task_now, task_id)
    
    return api_response(data={"message": f"任务 {task_id} 已开始执行"})


@router.post("/{task_id}/retry-notification")
async def retry_notification(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_admin)):
    from app.services.channel_service import send_configured
    scheduler = SchedulerService()
    task = await scheduler.get_task(task_id)
    if not task or (task.get("params") or {}).get("user_id") != user.id:
        raise HTTPException(404, "任务不存在或无权操作")
    result = task.get("result") or {}
    text = result.get("notification_text")
    if not text:
        raise HTTPException(400, "没有可补发的通知，请先执行任务")
    sent = await send_configured(db, user.id, task["params"].get("notify_channel"), text)
    obj = scheduler._tasks[task_id]
    obj.last_result = {**result, "notification_result": sent}
    scheduler._persist_task_state(obj)
    return api_response(data=sent)
