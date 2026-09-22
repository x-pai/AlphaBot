"""
市场缓存层（Redis）：所有市场领域缓存的唯一后端存储。

设计约束：
- key 统一带交易日锚点，避免跨日复用旧数据
- 不再降级为进程内存，Redis 不可达时抛出 503 对应异常
- “是否需要盘中刷新” 由 MarketDomainService 的读时策略决定
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any, Callable, Optional

from app.services.redis_service import get_async_redis_client

_redis = None
_redis_failed_until = 0.0


class MarketCacheUnavailable(RuntimeError):
    """Redis, the required market cache backend, is unavailable."""


def _mark_redis_failed() -> None:
    global _redis, _redis_failed_until
    _redis = None
    _redis_failed_until = time.time() + 30


async def _client():
    global _redis, _redis_failed_until
    if _redis is not None:
        return _redis
    now = time.time()
    if now < _redis_failed_until:
        raise MarketCacheUnavailable("Redis is temporarily unavailable")
    try:
        client = get_async_redis_client()
        await client.ping()
        _redis = client
        return client
    except Exception as exc:
        _mark_redis_failed()
        raise MarketCacheUnavailable("Redis connection failed") from exc

async def get_json(key: str) -> Optional[Any]:
    r = await _client()
    try:
        raw = await r.get(key)
    except Exception as exc:
        _mark_redis_failed()
        raise MarketCacheUnavailable("Redis read failed") from exc
    return json.loads(raw) if raw else None


async def set_json(key: str, value: Any, ttl: Optional[int] = None) -> None:
    raw = json.dumps(value, ensure_ascii=False)
    r = await _client()
    try:
        if ttl:
            await r.set(key, raw, ex=ttl)
        else:
            await r.set(key, raw)
    except Exception as exc:
        _mark_redis_failed()
        raise MarketCacheUnavailable("Redis write failed") from exc


async def overwrite_json(key: str, value: Any, ttl: Optional[int] = None) -> Any:
    resolved = await value if asyncio.iscoroutine(value) else value
    await set_json(key, resolved, ttl)
    return resolved


def sha1_of(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest()[:12]


def source_key(dataset: str, source: str, key: str) -> str:
    """按数据集和实际来源隔离缓存、刷新状态及 single-flight 锁。"""
    suffix = key.removeprefix("market:")
    versioned_source = "tdxaidata:v3" if source == "tdxaidata" else source
    return f"market:source:{dataset}:{versioned_source}:{suffix}"


_locks: dict[str, asyncio.Lock] = {}


def pool_key(kind: str, date: str) -> str:
    return f"market:pool:{kind}:{date}"


def universe_key() -> str:
    raise NotImplementedError("use universe_key_for_day")


def surge_key() -> str:
    raise NotImplementedError("use surge_key_for_day")


def universe_key_for_day(trade_date: str) -> str:
    return f"market:universe:{trade_date}"


def surge_key_for_day(trade_date: str) -> str:
    return f"market:surge:{trade_date}"


def quotes_key(symbols: list[str], trade_date: str) -> str:
    normalized = ",".join(sorted(dict.fromkeys(symbols)))
    return f"market:quotes:{sha1_of(normalized)}:{trade_date}"


def fundflow_key(codes: list[str], days: int, trade_date: str) -> str:
    normalized = ",".join(sorted(dict.fromkeys(codes)))
    return f"market:fundflow:{sha1_of(normalized)}:{days}:{trade_date}"


def members_key(plate_id: str, trade_date: str) -> str:
    return f"market:members:{plate_id}:{trade_date}"


def plate_index_key(plate_id: str, count: int, trade_date: str) -> str:
    return f"market:plate-index:{plate_id}:{count}:{trade_date}"


def trending_key(trade_date: str) -> str:
    return f"market:trending:{trade_date}"


def payoff_key(kind: str, date: str | None = None) -> str:
    return f"market:payoff:{kind}:{date or 'latest'}"


def turnover_key(trade_date: str) -> str:
    return f"market:turnover:{trade_date}"


async def cached_call(key: str, ttl: Optional[int], fetch: Callable[[], Any]) -> Any:
    """读时缓存（single-flight）：命中直接返回；未命中合并并发、拉取后写缓存。"""
    hit = await get_json(key)
    if hit is not None:
        return hit
    lock = _locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        await lock.acquire()
        lock.release()
        hit = await get_json(key)
        if hit is not None:
            return hit
    async with lock:
        hit = await get_json(key)
        if hit is not None:
            return hit
        payload = await fetch()
        await set_json(key, payload, ttl)
        return payload
