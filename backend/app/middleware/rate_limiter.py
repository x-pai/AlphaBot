"""
请求频率限制中间件
"""

import time
from typing import Dict, List, Tuple, Optional, Callable
import asyncio
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

# 全局变量，用于存储限制器实例
_limiters = {}
_cleanup_task = None
_lock = asyncio.Lock()

class RateLimiter:
    """请求频率限制器"""
    
    def __init__(self, limit_per_minute: int):
        """初始化限制器
        
        Args:
            limit_per_minute: 每分钟允许的请求数
        """
        self.limit_per_minute = limit_per_minute
        self.window_size = 60  # 窗口大小为60秒（1分钟）
        self.requests: Dict[str, List[float]] = {}  # 客户端请求时间戳记录
        self._lock = asyncio.Lock()  # 用于保护共享资源
    
    async def is_rate_limited(self, client_id: str) -> Tuple[bool, Optional[int]]:
        """检查客户端是否超过请求频率限制
        
        Args:
            client_id: 客户端标识（通常是IP地址）
            
        Returns:
            (is_limited, retry_after): 是否限制，以及需要等待的秒数
        """
        current_time = time.time()
        
        async with self._lock:
            # 获取客户端的请求记录
            client_requests = self.requests.get(client_id, [])
            
            # 清理过期的请求记录（超过窗口大小的）
            client_requests = [ts for ts in client_requests if current_time - ts < self.window_size]
            
            # 检查是否超过限制
            if len(client_requests) >= self.limit_per_minute:
                # 计算需要等待的时间
                oldest_request = min(client_requests)
                retry_after = int(self.window_size - (current_time - oldest_request))
                return True, max(1, retry_after)
            
            # 记录本次请求
            client_requests.append(current_time)
            self.requests[client_id] = client_requests
            
            return False, None
    
    async def cleanup(self):
        """清理过期的请求记录"""
        current_time = time.time()
        
        async with self._lock:
            for client_id in list(self.requests.keys()):
                self.requests[client_id] = [
                    ts for ts in self.requests[client_id] 
                    if current_time - ts < self.window_size
                ]
                
                # 如果客户端没有请求记录，则删除
                if not self.requests[client_id]:
                    del self.requests[client_id]

class RateLimitMiddleware(BaseHTTPMiddleware):
    """请求频率限制中间件"""
    
    def __init__(self, app: ASGIApp):
        """初始化中间件"""
        super().__init__(app)
        
        # 使用全局变量存储限制器实例
        global _limiters
        if not _limiters:
            _limiters = {
                "default": RateLimiter(settings.RATE_LIMIT_DEFAULT_MINUTE),
                "/api/v1/stocks/search": RateLimiter(settings.RATE_LIMIT_SEARCH_MINUTE),
                "/api/v1/stocks/": RateLimiter(settings.RATE_LIMIT_STOCK_INFO_MINUTE),
                "/api/v1/async/ai/analyze": RateLimiter(settings.RATE_LIMIT_AI_ANALYSIS_MINUTE),
                "/api/v1/ai/": RateLimiter(settings.RATE_LIMIT_AI_ANALYSIS_MINUTE),
                "/api/v1/tasks/": RateLimiter(settings.RATE_LIMIT_TASK_MINUTE),
            }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 如果禁用了请求频率限制，则直接处理请求
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # 获取客户端IP
        client_id = self._get_client_id(request)
        
        # 获取适用的限制器
        limiter = self._get_limiter(request.url.path)
        
        # 检查是否超过限制
        is_limited, retry_after = await limiter.is_rate_limited(client_id)
        
        if is_limited:
            # 返回 429 Too Many Requests
            return Response(
                content='{"detail": "Too many requests"}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after), "Content-Type": "application/json"}
            )
        
        # 处理请求
        return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用X-Forwarded-For头，适用于使用代理的情况
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 取第一个IP（最接近客户端的）
            return forwarded_for.split(",")[0].strip()
        
        # 否则使用客户端IP
        return request.client.host if request.client else "unknown"
    
    def _get_limiter(self, path: str) -> RateLimiter:
        """根据请求路径获取适用的限制器"""
        global _limiters
        # 检查路径是否匹配任何特定限制器
        for prefix, limiter in _limiters.items():
            if prefix != "default" and path.startswith(prefix):
                return limiter
        
        # 默认限制器
        return _limiters["default"]

# 启动清理任务
async def start_cleanup_task():
    """启动定期清理任务"""
    global _cleanup_task, _limiters, _lock
    
    async with _lock:
        if _cleanup_task is None:
            _cleanup_task = asyncio.create_task(_cleanup_loop())

# 停止清理任务
async def stop_cleanup_task():
    """停止定期清理任务"""
    global _cleanup_task, _lock
    
    async with _lock:
        if _cleanup_task:
            _cleanup_task.cancel()
            try:
                await _cleanup_task
            except asyncio.CancelledError:
                pass
            _cleanup_task = None

# 清理循环
async def _cleanup_loop():
    """定期清理过期的请求记录"""
    global _limiters
    
    while True:
        try:
            # 清理所有限制器
            for limiter in _limiters.values():
                await limiter.cleanup()
            
            # 每分钟清理一次
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"清理请求记录时出错: {str(e)}")
            await asyncio.sleep(60)  # 出错后等待较长时间 