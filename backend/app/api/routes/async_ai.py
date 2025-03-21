from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from celery.result import AsyncResult

from app.db.session import get_db
from app.tasks.ai_tasks import analyze_stock_task, analyze_time_series_task, analyze_intraday_task
from app.schemas.task import CeleryTaskStatus, CeleryTaskCreate
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit

router = APIRouter()

@router.post("/analyze", response_model=dict)
async def create_stock_analysis_task(
    task: CeleryTaskCreate,
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """创建股票分析异步任务"""
    try:
        if task.task_type == "stock_analysis":
            celery_task = analyze_stock_task.delay(
                task.symbol, task.data_source, task.analysis_type
            )
        elif task.task_type == "time_series":
            if not task.interval or not task.range:
                return api_response(success=False, error="时间序列分析需要指定interval和range参数")
            
            celery_task = analyze_time_series_task.delay(
                task.symbol, task.interval, task.range, 
                task.data_source, task.analysis_type
            )
        elif task.task_type == "intraday":
            celery_task = analyze_intraday_task.delay(
                task.symbol, task.data_source, task.analysis_type
            )
        else:
            return api_response(success=False, error="不支持的任务类型")
        
        return api_response(data={
            "task_id": celery_task.id,
            "status": "pending",
            "message": f"已创建{task.task_type}分析任务"
        })
    except Exception as e:
        return api_response(success=False, error=f"创建任务失败: {str(e)}")

@router.get("/task/{task_id}", response_model=dict)
async def get_task_status(
    task_id: str,
    _: None = Depends(check_usage_limit)
):
    """获取任务状态"""
    try:
        task_result = AsyncResult(task_id)
        # 初始化响应数据
        response_data = {
            "task_id": task_id,
            "status": task_result.state,
            "message": ""
        }
        status = task_result.result.get('status') if isinstance(task_result.result, dict) else None
        analysis = task_result.result.get('analysis') if isinstance(task_result.result, dict) else None

        # 根据不同状态构建响应数据
        if task_result.state == 'PENDING':
            response_data["message"] = "任务正在等待执行"
        elif task_result.state == 'STARTED':
            response_data["message"] = "任务正在执行中"
        elif task_result.state == 'SUCCESS':
            # 任务成功完成，获取结果
            response_data["message"] = status
            response_data["result"] = analysis
        elif task_result.state == 'FAILURE':
            # 任务失败，获取错误信息
            error = str(task_result.result)
            response_data["message"] = f"任务执行失败: {error}"
        elif task_result.state == 'REVOKED':
            response_data["message"] = "任务已被取消"  
        else:
            response_data["message"] = status
        
        return api_response(data=response_data)
    except Exception as e:
        return api_response(success=False, error=f"获取任务状态失败: {str(e)}")

@router.delete("/task/{task_id}", response_model=dict)
async def cancel_task(
    task_id: str,
    _: None = Depends(check_usage_limit)
):
    """取消任务"""
    try:
        task = AsyncResult(task_id)
        task.revoke(terminate=True)
        return api_response(data={
            "task_id": task_id,
            "status": "canceled",  # 使用前端期望的状态名称
            "message": "任务已取消"
        })
    except Exception as e:
        return api_response(success=False, error=f"取消任务失败: {str(e)}") 