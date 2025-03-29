from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class TaskBase(BaseModel):
    """任务基础模型"""
    interval: int = Field(3600, description="任务执行间隔（秒）")
    is_enabled: bool = Field(True, description="任务是否启用")
    description: str = Field("", description="任务描述")

class TaskCreate(TaskBase):
    """创建任务模型"""
    task_type: str = Field(..., description="任务类型")
    symbol: Optional[str] = Field(None, description="股票代码")
    params: Dict[str, Any] = Field(default_factory=dict, description="任务参数")

class TaskUpdate(BaseModel):
    """更新任务模型"""
    interval: Optional[int] = Field(None, description="任务执行间隔（秒）")
    is_enabled: Optional[bool] = Field(None, description="任务是否启用")
    description: Optional[str] = Field(None, description="任务描述")
    params: Optional[Dict[str, Any]] = Field(None, description="任务参数")

class TaskInfo(TaskBase):
    """任务信息模型"""
    task_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    next_run: Optional[datetime] = Field(None, description="下次运行时间")
    last_run: Optional[datetime] = Field(None, description="上次运行时间")
    run_count: int = Field(0, description="运行次数")
    status: str = Field("pending", description="任务状态")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    params: Dict[str, Any] = Field(default_factory=dict, description="任务参数")

    class Config:
        from_attributes = True

# 新增Celery任务相关模型
class CeleryTaskStatus(BaseModel):
    """Celery任务状态模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态：PENDING, STARTED, SUCCESS, FAILURE, PROGRESS")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    progress: Optional[float] = Field(None, description="进度百分比")
    message: Optional[str] = Field(None, description="状态消息")
    error: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class CeleryTaskCreate(BaseModel):
    """创建Celery任务请求模型"""
    task_type: str = Field(..., description="任务类型: stock_analysis, time_series, intraday")
    symbol: Union[str, List[str]] = Field(..., description="股票代码或股票代码列表")
    analysis_type: Optional[str] = Field("llm", description="分析类型: rule, ml, llm")
    data_source: Optional[str] = Field(None, description="数据源")
    interval: Optional[str] = Field(None, description="时间间隔 (仅time_series)")
    range: Optional[str] = Field(None, description="时间范围 (仅time_series)") 