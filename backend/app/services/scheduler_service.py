import asyncio
import time
from typing import Dict, Any, List, Callable, Awaitable, Optional
from datetime import datetime, timedelta
import logging
import uuid
import inspect
import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.task import ScheduledTask

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("uvicorn")

class Task:
    """定时任务"""
    def __init__(
        self, 
        task_id: str,
        func: Callable[..., Awaitable[Any]], 
        args: List[Any] = None, 
        kwargs: Dict[str, Any] = None,
        interval: int = 3600,  # 默认1小时
        next_run: float = None,
        description: str = "",
        is_enabled: bool = True,
        task_type: str = "generic",
        params: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.interval = interval
        self.next_run = next_run or time.time()
        self.description = description
        self.is_enabled = is_enabled
        self.task_type = task_type
        self.params = params or {}
        self.last_run = None
        self.last_result = None
        self.last_error = None
        self.run_count = 0
        self.status = "pending"
        self.current_stage = None
        self.status_detail = None
        self.stage_history: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为可序列化的字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "interval": self.interval,
            "next_run": datetime.fromtimestamp(self.next_run).isoformat() if self.next_run else None,
            "description": self.description,
            "is_enabled": self.is_enabled,
            "last_run": datetime.fromtimestamp(self.last_run).isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "status": self.status,
            "current_stage": self.current_stage,
            "status_detail": self.status_detail,
            "stage_history": self.stage_history,
            "result": self.last_result if isinstance(self.last_result, dict) else {"value": self.last_result} if self.last_result is not None else None,
            "error": self.last_error,
            "params": self.params,
        }

class SchedulerService:
    """定时任务调度服务"""
    
    _instance = None
    _lock = asyncio.Lock()  # 添加锁以保护共享资源
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerService, cls).__new__(cls)
            cls._instance._tasks: Dict[str, Task] = {}
            cls._instance._running = False
            cls._instance._task_loop = None
            cls._instance._task_lock = asyncio.Lock()  # 添加任务锁
        return cls._instance

    def _db(self) -> Session:
        return SessionLocal()

    @staticmethod
    def _timestamp_to_datetime(value: Optional[float]) -> Optional[datetime]:
        if value is None:
            return None
        return datetime.fromtimestamp(value)

    @staticmethod
    def _datetime_to_timestamp(value: Optional[datetime]) -> Optional[float]:
        if value is None:
            return None
        return value.timestamp()

    def _hydrate_task_from_record(
        self,
        record: ScheduledTask,
        func: Callable[..., Awaitable[Any]],
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Task:
        task = Task(
            task_id=record.task_id,
            func=func,
            args=args or [],
            kwargs=kwargs or {},
            interval=record.interval,
            next_run=self._datetime_to_timestamp(record.next_run),
            description=record.description,
            is_enabled=record.is_enabled,
            task_type=record.task_type,
            params=record.params or {},
        )
        task.last_run = self._datetime_to_timestamp(record.last_run)
        task.run_count = record.run_count or 0
        task.status = record.status or "pending"
        task.current_stage = record.current_stage
        task.status_detail = record.status_detail
        task.stage_history = record.stage_history or []
        task.last_result = record.last_result
        task.last_error = record.last_error
        return task

    def _persist_task_state(self, task: Task) -> None:
        db = self._db()
        try:
            record = db.query(ScheduledTask).filter(ScheduledTask.task_id == task.task_id).first()
            if not record:
                record = ScheduledTask(task_id=task.task_id)
                db.add(record)

            record.task_type = task.task_type
            record.interval = task.interval
            record.next_run = self._timestamp_to_datetime(task.next_run)
            record.description = task.description
            record.is_enabled = task.is_enabled
            record.params = task.params or {}
            record.last_run = self._timestamp_to_datetime(task.last_run)
            record.run_count = task.run_count
            record.status = task.status
            record.current_stage = task.current_stage
            record.status_detail = task.status_detail
            record.stage_history = task.stage_history or []
            record.last_result = task.last_result
            record.last_error = task.last_error
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _remove_persisted_task_state(self, task_id: str) -> None:
        db = self._db()
        try:
            record = db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
            if record:
                db.delete(record)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _load_persisted_task_record(self, task_id: str) -> Optional[ScheduledTask]:
        db = self._db()
        try:
            return db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
        finally:
            db.close()

    def restore_tasks_from_db(
        self,
        task_factories: Dict[str, Dict[str, Any]],
    ) -> None:
        db = self._db()
        try:
            records = db.query(ScheduledTask).all()
            for record in records:
                if record.task_id in self._tasks:
                    continue

                factory = task_factories.get(record.task_type)
                if not factory:
                    logger.warning("跳过未知任务类型的恢复: %s (%s)", record.task_id, record.task_type)
                    continue

                kwargs = dict(factory.get("kwargs") or {})
                args = list(factory.get("args") or [])
                if record.task_type == "skill_publish_job":
                    kwargs["task_id"] = record.task_id
                    kwargs["params"] = record.params or {}
                elif record.task_type == "update_stock_data":
                    symbol = (record.params or {}).get("symbol")
                    args = [symbol] if symbol else []

                task = self._hydrate_task_from_record(
                    record,
                    func=factory["func"],
                    args=args,
                    kwargs=kwargs,
                )
                self._tasks[record.task_id] = task
        finally:
            db.close()
    
    async def add_task(
        self, 
        func: Callable[..., Awaitable[Any]], 
        args: List[Any] = None, 
        kwargs: Dict[str, Any] = None,
        interval: int = 3600,
        next_run: float = None,
        description: str = "",
        task_id: str = None,
        is_enabled: bool = True,
        task_type: str = "generic",
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """添加定时任务"""
        # 生成任务ID
        task_id = task_id or str(uuid.uuid4())
        
        # 创建任务
        task = Task(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            interval=interval,
            next_run=next_run,
            description=description,
            is_enabled=is_enabled,
            task_type=task_type,
            params=params,
        )

        persisted = self._load_persisted_task_record(task_id)
        if persisted:
            task.interval = persisted.interval
            task.next_run = self._datetime_to_timestamp(persisted.next_run) or task.next_run
            task.description = persisted.description
            task.is_enabled = persisted.is_enabled
            task.params = persisted.params or {}
            if isinstance(task.kwargs.get("params"), dict):
                task.kwargs["params"] = task.params
            task.last_run = self._datetime_to_timestamp(persisted.last_run)
            task.run_count = persisted.run_count or 0
            task.status = persisted.status or task.status
            task.current_stage = persisted.current_stage
            task.status_detail = persisted.status_detail
            task.stage_history = persisted.stage_history or []
            task.last_result = persisted.last_result
            task.last_error = persisted.last_error

        # 添加到任务列表
        async with self._task_lock:
            self._tasks[task_id] = task

        self._persist_task_state(task)
        
        logger.info(f"添加任务: {task_id} - {description}")
        return task_id
    
    async def remove_task(self, task_id: str) -> bool:
        """移除定时任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._remove_persisted_task_state(task_id)
                logger.info(f"移除任务: {task_id}")
                return True
        return False
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        async with self._task_lock:
            task = self._tasks.get(task_id)
            return task.to_dict() if task else None
    
    async def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务"""
        async with self._task_lock:
            return [task.to_dict() for task_id, task in self._tasks.items()]
    
    async def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].is_enabled = True
                self._persist_task_state(self._tasks[task_id])
                logger.info(f"启用任务: {task_id}")
                return True
        return False
    
    async def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].is_enabled = False
                self._persist_task_state(self._tasks[task_id])
                logger.info(f"禁用任务: {task_id}")
                return True
        return False

    async def update_task(
        self,
        task_id: str,
        interval: Optional[int] = None,
        next_run: Optional[float] = None,
        is_enabled: Optional[bool] = None,
        description: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新任务的调度配置。"""
        async with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if interval is not None:
                task.interval = interval
                task.next_run = next_run if next_run is not None else time.time() + interval
            elif next_run is not None:
                task.next_run = next_run

            if is_enabled is not None:
                task.is_enabled = is_enabled

            if description is not None:
                task.description = description

            if params is not None:
                task.params = params
                if isinstance(task.kwargs.get("params"), dict):
                    task.kwargs["params"] = params

            self._persist_task_state(task)

            logger.info(
                "更新任务: %s - interval=%s is_enabled=%s",
                task_id,
                task.interval,
                task.is_enabled,
            )
            return True
    
    def update_task_interval(self, task_id: str, interval: int) -> bool:
        """更新任务间隔"""
        if task_id in self._tasks:
            self._tasks[task_id].interval = interval
            logger.info(f"更新任务间隔: {task_id} - {interval}秒")
            return True
        return False

    def _build_progress_callback(self, task: Task):
        async def _progress_callback(stage: str, detail: Optional[str] = None, payload: Optional[Dict[str, Any]] = None):
            task.current_stage = stage
            task.status_detail = detail
            task.status = "running"
            task.stage_history.append({
                "stage": stage,
                "detail": detail,
                "timestamp": datetime.now().isoformat(),
                "payload": payload or {},
            })
            # 保留最近 20 条阶段记录，避免无限增长
            task.stage_history = task.stage_history[-20:]
            if payload:
                existing = task.last_result if isinstance(task.last_result, dict) else {}
                task.last_result = {
                    **existing,
                    "progress": {
                        "stage": stage,
                        "detail": detail,
                        **payload,
                    },
                }
            self._persist_task_state(task)
        return _progress_callback

    async def _invoke_task(self, task: Task):
        kwargs = dict(task.kwargs or {})
        try:
            signature = inspect.signature(task.func)
            if "progress_callback" in signature.parameters:
                kwargs["progress_callback"] = self._build_progress_callback(task)
        except Exception:
            pass
        result = await task.func(*task.args, **kwargs)
        # 在更新任务状态前转换并校验，避免不可序列化的结果让失败状态也无法入库。
        try:
            result = jsonable_encoder(result)
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"任务结果无法序列化为 JSON: {exc}") from exc
        return result
    
    async def run_task_now(self, task_id: str) -> bool:
        """立即运行任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        
        try:
            task.last_result = None
            task.last_error = None
            task.status = "running"
            task.current_stage = "queued"
            task.status_detail = "任务已启动，等待执行。"
            task.stage_history = []
            self._persist_task_state(task)
            logger.info(f"手动运行任务: {task_id} - {task.description}")
            task.last_result = await self._invoke_task(task)
            task.last_run = time.time()
            task.run_count += 1
            task.last_error = None
            task.status = "success"
            task.current_stage = "completed"
            task.status_detail = "任务执行完成。"
            self._persist_task_state(task)
            return True
        except Exception as e:
            task.last_error = str(e)
            task.status = "failed"
            task.current_stage = "failed"
            task.status_detail = str(e)
            self._persist_task_state(task)
            logger.error(f"任务执行出错: {task_id} - {str(e)}")
            return False
    
    async def start(self):
        """启动调度器"""
        async with self._lock:
            if self._running:
                logger.info("调度器已经在运行中")
                return
            
            self._running = True
            logger.info("启动调度器")
            
            # 创建异步任务
            self._task_loop = asyncio.create_task(self._run_scheduler())
    
    async def stop(self):
        """停止调度器"""
        async with self._lock:
            if not self._running:
                logger.info("调度器未在运行")
                return
            
            self._running = False
            logger.info("停止调度器")
            
            # 取消异步任务
            if self._task_loop:
                self._task_loop.cancel()
                try:
                    await self._task_loop
                except asyncio.CancelledError:
                    pass
                self._task_loop = None
    
    async def _run_scheduler(self):
        """运行调度器主循环"""
        logger.info("调度器主循环开始运行")
        
        while self._running:
            try:
                # 获取当前时间
                now = time.time()
                
                # 查找需要执行的任务
                tasks_to_run = []
                async with self._task_lock:
                    for task_id, task in self._tasks.items():
                        if task.is_enabled and task.next_run <= now:
                            tasks_to_run.append(task)
                            # 更新下次运行时间
                            task.next_run = now + task.interval
                            self._persist_task_state(task)
                
                # 执行任务
                for task in tasks_to_run:
                    asyncio.create_task(self._execute_task(task))
                
                # 等待一段时间
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"调度器运行出错: {str(e)}")
                await asyncio.sleep(5)  # 出错后等待较长时间
    
    async def _execute_task(self, task: Task):
        """执行任务"""
        task.last_run = time.time()
        task.run_count += 1
        task.last_result = None
        task.last_error = None
        task.status = "running"
        task.current_stage = "queued"
        task.status_detail = "等待后台执行。"
        task.stage_history = []
        self._persist_task_state(task)
        
        try:
            # 执行任务函数
            result = await self._invoke_task(task)
            task.last_result = result
            task.last_error = None
            task.status = "success"
            task.current_stage = "completed"
            task.status_detail = "任务执行完成。"
            self._persist_task_state(task)
            logger.info(f"任务执行成功: {task.task_id} - {task.description}")
            return result
        except Exception as e:
            task.last_error = str(e)
            task.status = "failed"
            task.current_stage = "failed"
            task.status_detail = str(e)
            self._persist_task_state(task)
            logger.error(f"任务执行失败: {task.task_id} - {task.description} - {str(e)}")
            return None 
