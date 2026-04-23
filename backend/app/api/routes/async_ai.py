from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from celery.result import AsyncResult

from app.db.session import get_db
from app.tasks.ai_tasks import analyze_stock_task, analyze_time_series_task, analyze_intraday_task, batch_analyze_time_series_task
from app.schemas.task import CeleryTaskCreate
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit
from app.models.user import User
from app.services.batch_analysis_limiter import BatchAnalysisLimiter
from app.utils.symbol_utils import normalize_stock_symbols

router = APIRouter()
MAX_BATCH_ANALYSIS_SYMBOLS = 10

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
    current_user: User = Depends(check_usage_limit)
):
    """获取任务状态"""
    try:
        task_result = AsyncResult(task_id)
        task_info = task_result.info if isinstance(task_result.info, dict) else {}
        task_payload = task_result.result if isinstance(task_result.result, dict) else {}

        # 初始化响应数据
        response_data = {
            "task_id": task_id,
            "status": task_result.state,
            "message": "",
            "progress": task_info.get("progress"),
            "current_symbol": task_info.get("current_symbol"),
            "completed": task_info.get("completed"),
            "total": task_info.get("total"),
            "report_url": task_info.get("report_url"),
            "errors": task_info.get("errors", {}),
            "successful_analyses": task_info.get("successful_analyses"),
            "failed_analyses": task_info.get("failed_analyses"),
            "results": task_info.get("results", {}),
        }
        status = task_payload.get('status')
        analysis = task_payload.get('analysis')

        # 根据不同状态构建响应数据
        if task_result.state == 'PENDING':
            response_data["message"] = "任务正在等待执行"
        elif task_result.state == 'STARTED':
            response_data["message"] = "任务正在执行中"
        elif task_result.state == 'PROGRESS':
            response_data["message"] = task_info.get("status") or "任务正在执行中"
        elif task_result.state == 'SUCCESS':
            # 任务成功完成，获取结果
            response_data["message"] = task_payload.get("message") or status or "任务已完成"
            response_data["result"] = task_payload.get("result", analysis)
            response_data["progress"] = task_payload.get("progress", 100)
            response_data["current_symbol"] = task_payload.get("current_symbol")
            response_data["completed"] = task_payload.get("completed")
            response_data["total"] = task_payload.get("total")
            response_data["report_url"] = task_payload.get("report_url")
            response_data["errors"] = task_payload.get("errors", {})
            response_data["successful_analyses"] = task_payload.get("successful_analyses")
            response_data["failed_analyses"] = task_payload.get("failed_analyses")
            response_data["results"] = task_payload.get("results", {})
        elif task_result.state == 'FAILURE':
            # 任务失败，获取错误信息
            error = str(task_result.result)
            response_data["message"] = f"任务执行失败: {error}"
        elif task_result.state == 'REVOKED':
            response_data["message"] = "任务已被取消"  
        else:
            response_data["message"] = status

        if task_result.state in {'SUCCESS', 'FAILURE', 'REVOKED'}:
            await BatchAnalysisLimiter.clear_running_task(current_user.id, task_id)
        
        return api_response(data=response_data)
    except Exception as e:
        return api_response(success=False, error=f"获取任务状态失败: {str(e)}")

@router.delete("/task/{task_id}", response_model=dict)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(check_usage_limit)
):
    """取消任务"""
    try:
        task = AsyncResult(task_id)
        task.revoke(terminate=True)
        await BatchAnalysisLimiter.clear_running_task(current_user.id, task_id)
        return api_response(data={
            "task_id": task_id,
            "status": "canceled",  # 使用前端期望的状态名称
            "message": "任务已取消"
        })
    except Exception as e:
        return api_response(success=False, error=f"取消任务失败: {str(e)}")

@router.post("/batch-analyze", response_model=dict)
async def create_batch_analysis_task(
    task: CeleryTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_usage_limit)
):
    """创建批量股票分析异步任务"""
    try:
        if not isinstance(task.symbol, list):
            return api_response(success=False, error="批量分析需要提供股票代码列表")

        running_task_id = await BatchAnalysisLimiter.get_running_task_id(current_user.id)
        if running_task_id:
            return api_response(
                success=False,
                error="已有批量分析任务正在运行，请等待当前任务完成后再提交"
            )

        cooldown_seconds = await BatchAnalysisLimiter.get_cooldown_seconds(current_user.id)
        if cooldown_seconds > 0:
            return api_response(
                success=False,
                error=f"提交过于频繁，请在 {cooldown_seconds} 秒后再试"
            )

        normalized_symbols, invalid_symbols = normalize_stock_symbols(task.symbol)

        if invalid_symbols:
            invalid_display = "、".join(invalid_symbols[:3])
            suffix = " 等" if len(invalid_symbols) > 3 else ""
            return api_response(
                success=False,
                error=f"存在无效股票代码: {invalid_display}{suffix}"
            )

        if len(normalized_symbols) == 0:
            return api_response(success=False, error="请至少提供一个股票代码")

        if len(normalized_symbols) > MAX_BATCH_ANALYSIS_SYMBOLS:
            return api_response(
                success=False,
                error=f"批量分析一次最多支持 {MAX_BATCH_ANALYSIS_SYMBOLS} 个股票"
            )
            
        if task.task_type == "time_series":
            if not task.interval or not task.range:
                return api_response(success=False, error="时间序列分析需要指定interval和range参数")
            
            celery_task = batch_analyze_time_series_task.delay(
                normalized_symbols,
                task.interval,
                task.range,
                task.data_source,
                task.analysis_type
            )
            await BatchAnalysisLimiter.register_submission(current_user.id, celery_task.id)
        else:
            return api_response(success=False, error="不支持的批量分析类型")
        
        return api_response(data={
            "task_id": celery_task.id,
            "status": "pending",
            "message": f"已创建批量{task.task_type}分析任务"
        })
    except Exception as e:
        return api_response(success=False, error=f"创建批量分析任务失败: {str(e)}") 
