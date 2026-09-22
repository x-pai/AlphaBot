"""
市场数据源基类：按领域定义采集接口与领域 schema。

领域对象与前端契约逐字段对齐（fund 单位元、time 为当日分钟数、change 为 %）；
换数据源 = 实现 MarketDataSourceBase + 在 factory 绑定对应数据集。
"""

from __future__ import annotations

import asyncio
from abc import ABC
from typing import Any, Dict, List, Optional, TypedDict

import httpx

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_client: httpx.AsyncClient | None = None


def http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=25, headers={"Accept": "application/json", "User-Agent": _UA})
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def get_with_retry(url: str, params: dict[str, Any] | None = None, attempts: int = 3) -> httpx.Response:
    """上游 GET：连接/读超时自动重试（幂等请求），指数退避。"""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = await http_client().get(url, params=params)
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(0.8 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def normalize_code(symbol: str) -> str | None:
    code = (symbol or "").strip()
    for suffix in (".SS", ".SZ", ".SH", ".BJ", ".HK", ".US"):
        if code.upper().endswith(suffix):
            code = code[: -len(suffix)]
            break
    if code.upper().startswith(("SH", "SZ", "BJ")):
        code = code[2:]
    code = code.zfill(6)
    return code if len(code) == 6 and code != "000000" else None


def num(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0  # NaN 过滤


class PoolItem(TypedDict, total=False):
    """涨停/炸板/跌停池条目（前端 TopicStock 契约）。"""

    name: str
    code: str
    reason: str
    concepts: Optional[List[str]]
    lbc: int
    time: int | None
    type: str  # 'zt' | 'zb' | 'dt'
    fund: int | None  # 元
    price: float | None
    turnoverRate: float  # %
    zbc: int
    firstBreak: Optional[int]
    lastSealTs: Optional[int]


class PlateItem(TypedDict, total=False):
    """板块宇宙条目（前端 PlateFlow 契约）。"""

    code: str
    name: str
    change: float | None
    netFlow: float | None  # 亿
    ztCount: int | None
    upCount: int | None
    downCount: int | None
    flatCount: int | None


class SurgeItem(TypedDict, total=False):
    """异动池条目（前端 SurgeLimitStock 契约）。"""

    code: str
    name: str
    plates: List[str]
    analysis: Optional[str]


class QuoteItem(TypedDict, total=False):
    """实时行情快照。"""

    name: str
    price: Optional[float]
    change: float  # %


class FundflowRow(TypedDict, total=False):
    """个股逐日资金流行（单位万元，与前端 FundflowRow 契约一致）。"""

    prodCode: str
    date: str
    mainIn: float
    mainOut: float
    netInflow: float
    superIn: float
    superOut: float
    netSuper: float
    bigIn: float
    bigOut: float
    netBig: float
    mediumIn: float
    mediumOut: float
    netMedium: float
    smallIn: float
    smallOut: float
    netSmall: float


class MemberItem(TypedDict, total=False):
    """板块成员（成分 + 实时行情合成，前端 PlateMember 契约）。"""

    code: str
    name: str
    price: float | None
    change: float | None  # %
    amount: float | None  # 亿
    netFlow: float | None  # 亿
    turnoverRate: float | None  # %


class IndexBarItem(TypedDict, total=False):
    """板块指数日线（前端 IndexBar 契约）。"""

    date: str  # YYYYMMDD
    open: float
    close: float
    high: float
    low: float


class PayoffRawItem(TypedDict, total=False):
    """赚钱效应名单的归一化原始项（格式化在前端）。"""

    name: str
    change: float  # %
    plate: str  # strong
    days: int  # strong
    boards: int  # strong
    rank: int  # tdxaidata 人气名次
    heat: float | None  # hot（万）
    tag: str  # hot
    maxDrawdown: float  # bigface
    industryBlock: str  # bigface


class TurnoverData(TypedDict, total=False):
    """成交额分钟数据（数值域；中文格式化在前端）。"""

    current: Optional[float]
    predict: Optional[float]
    previous: Optional[float]
    change: Optional[float]
    points: List[Dict[str, Any]]


class TrendingPlateItem(TypedDict, total=False):
    """趋势板块推荐（催化层）。"""

    plateId: str
    name: str
    description: Optional[str]
    stocks: List[Dict[str, Any]]


class MarketDataSourceBase(ABC):
    """未实现的方法默认抛 NotImplementedError——per-dataset 绑定下允许部分实现。"""

    """市场数据源抽象基类：换数据源 = 继承本类并实现全部领域方法。"""

    SUPPORTED_DATASETS: frozenset[str] = frozenset()

    async def fetch_pool(self, kind: str, date: Optional[str] = None) -> List[PoolItem]:
        """涨停/炸板/跌停池。kind ∈ {'zt','zb','dt'}；date 为 YYYYMMDD。"""
        raise NotImplementedError

    async def fetch_universe(self) -> List[PlateItem]:
        """板块宇宙（全量，按核心涨跌幅降序）。"""
        raise NotImplementedError

    async def fetch_surge(self) -> List[SurgeItem]:
        """异动池。"""
        raise NotImplementedError

    async def fetch_quotes(self, codes: List[str]) -> Dict[str, QuoteItem]:
        """批量实时行情快照，按 6 位代码键控。"""
        raise NotImplementedError

    async def fetch_fundflow(self, codes: List[str], days: int) -> Dict[str, List[FundflowRow]]:
        """个股逐日资金流（day_count 上限 10），按 6 位代码键控。"""
        raise NotImplementedError

    async def fetch_members(self, plate_id: str) -> List[MemberItem]:
        """板块成员（成分 + 实时行情合成）。"""
        raise NotImplementedError

    async def fetch_plate_index(self, plate_id: str, count: int) -> List[IndexBarItem]:
        """板块指数日线。"""
        raise NotImplementedError

    async def fetch_payoff(self, kind: str, date: Optional[str] = None) -> List[PayoffRawItem]:
        """赚钱效应名单。kind ∈ {'strong','hot','drawdown'}。"""
        raise NotImplementedError

    async def fetch_turnover(self) -> TurnoverData:
        """成交额分钟数据（数值域）。"""
        raise NotImplementedError

    async def fetch_trending(self) -> List[TrendingPlateItem]:
        """趋势板块推荐（催化层）。"""
        raise NotImplementedError
