from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.services.scheduler_service import SchedulerService
from app.services.stock_service import StockService
from app.schemas.task import TaskCreate, TaskUpdate, TaskInfo
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit

router = APIRouter()

# 创建一个包装函数，在任务执行时获取数据库会话
async def update_stock_data_with_db(symbol: str = None):
    """包装函数，在执行时创建数据库会话"""
    db = SessionLocal()
    try:
        return await StockService.update_stock_data(symbol, db)
    finally:
        db.close()

@router.get("", response_model=dict)
async def get_all_tasks():
    """获取所有定时任务"""
    scheduler = SchedulerService()
    tasks = await scheduler.get_all_tasks()
    return api_response(data=tasks)

@router.get("/{task_id}", response_model=dict)
async def get_task(task_id: str):
    """获取特定定时任务"""
    scheduler = SchedulerService()
    task = await scheduler.get_task(task_id)
    if not task:
        return api_response(success=False, error="任务不存在")
    return api_response(data=task)

@router.post("", response_model=dict)
async def create_task(
    task: TaskCreate,
    _: None = Depends(check_usage_limit)
):
    """创建定时任务"""
    scheduler = SchedulerService()
    
    # 目前只支持更新股票数据的任务
    if task.task_type != "update_stock_data":
        return api_response(success=False, error="不支持的任务类型")
    
    # 创建任务
    task_id = await scheduler.add_task(
        func=update_stock_data_with_db,
        args=[task.symbol] if task.symbol else [],
        interval=task.interval,
        description=f"更新股票数据: {task.symbol if task.symbol else '所有'}",
        is_enabled=task.is_enabled
    )
    
    if not task_id:
        return api_response(success=False, error="创建任务失败")
    
    # 获取创建的任务信息
    new_task = await scheduler.get_task(task_id)
    return api_response(data=new_task)

@router.put("/{task_id}", response_model=dict)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    _: None = Depends(check_usage_limit)
):
    """更新定时任务"""
    scheduler = SchedulerService()
    
    # 检查任务是否存在
    if not await scheduler.get_task(task_id):
        return api_response(success=False, error="任务不存在")
    
    # 更新任务
    success = await scheduler.update_task(
        task_id=task_id,
        interval=task_update.interval,
        is_enabled=task_update.is_enabled
    )
    
    if not success:
        return api_response(success=False, error="更新任务失败")
    
    # 获取更新后的任务信息
    updated_task = await scheduler.get_task(task_id)
    return api_response(data=updated_task)

@router.delete("/{task_id}", response_model=dict)
async def delete_task(task_id: str):
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
    _: None = Depends(check_usage_limit)
):
    """立即运行定时任务"""
    scheduler = SchedulerService()
    
    # 检查任务是否存在
    task = await scheduler.get_task(task_id)
    if not task:
        return api_response(success=False, error="任务不存在")
    
    # 在后台运行任务
    background_tasks.add_task(scheduler.run_task_now, task_id)
    
    return api_response(data={"message": f"任务 {task_id} 已开始执行"})

@router.post("/update-stock/{symbol}")
async def update_stock_data(
    symbol: str,
    background_tasks: BackgroundTasks,
    _: None = Depends(check_usage_limit)
):
    """手动更新特定股票数据"""
    background_tasks.add_task(update_stock_data_with_db, symbol)
    return {"success": True, "data": {"message": f"开始更新股票 {symbol} 的数据"}}

@router.post("/update-all-stocks")
async def update_all_stocks(
    background_tasks: BackgroundTasks,
    _: None = Depends(check_usage_limit)
):
    """手动更新所有股票数据"""
    background_tasks.add_task(update_stock_data_with_db)
    return {"success": True, "data": {"message": "开始更新所有股票数据"}} 