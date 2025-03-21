import asyncio
import time
from typing import Dict, Any, List, Callable, Awaitable, Optional
from datetime import datetime, timedelta
import logging
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("scheduler")

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
        is_enabled: bool = True
    ):
        self.task_id = task_id
        self.func = func
        self.args = args or []
        self.kwargs = kwargs or {}
        self.interval = interval
        self.next_run = next_run or time.time()
        self.description = description
        self.is_enabled = is_enabled
        self.last_run = None
        self.last_result = None
        self.last_error = None
        self.run_count = 0

    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为可序列化的字典"""
        return {
            "task_id": self.task_id,
            "interval": self.interval,
            "next_run": self.next_run,
            "description": self.description,
            "is_enabled": self.is_enabled,
            "last_run": self.last_run,
            "last_result": str(self.last_result) if self.last_result is not None else None,
            "last_error": self.last_error,
            "run_count": self.run_count,
            # 不包含 func, args, kwargs 因为它们不可序列化
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
    
    async def add_task(
        self, 
        func: Callable[..., Awaitable[Any]], 
        args: List[Any] = None, 
        kwargs: Dict[str, Any] = None,
        interval: int = 3600,
        description: str = "",
        task_id: str = None,
        is_enabled: bool = True
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
            description=description,
            is_enabled=is_enabled
        )
        
        # 添加到任务列表
        async with self._task_lock:
            self._tasks[task_id] = task
        
        logger.info(f"添加任务: {task_id} - {description}")
        return task_id
    
    async def remove_task(self, task_id: str) -> bool:
        """移除定时任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
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
                logger.info(f"启用任务: {task_id}")
                return True
        return False
    
    async def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        async with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].is_enabled = False
                logger.info(f"禁用任务: {task_id}")
                return True
        return False
    
    def update_task_interval(self, task_id: str, interval: int) -> bool:
        """更新任务间隔"""
        if task_id in self._tasks:
            self._tasks[task_id].interval = interval
            logger.info(f"更新任务间隔: {task_id} - {interval}秒")
            return True
        return False
    
    async def run_task_now(self, task_id: str) -> bool:
        """立即运行任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        
        try:
            logger.info(f"手动运行任务: {task_id} - {task.description}")
            task.last_result = await task.func(*task.args, **task.kwargs)
            task.last_run = time.time()
            task.run_count += 1
            task.last_error = None
            return True
        except Exception as e:
            task.last_error = str(e)
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
        
        try:
            # 执行任务函数
            result = await task.func(*task.args, **task.kwargs)
            task.last_result = result
            logger.info(f"任务执行成功: {task.task_id} - {task.description}")
            return result
        except Exception as e:
            task.last_error = str(e)
            logger.error(f"任务执行失败: {task.task_id} - {task.description} - {str(e)}")
            return None 