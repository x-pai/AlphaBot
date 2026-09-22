from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None


class TradingCalendarData(BaseModel):
    days: list[str]
    latest_trading_day: str | None = None


class IntradayEmotionPoint(BaseModel):
    time: str
    positive: float | None = None
    negative: float | None = None
    index: float | None = None


class IntradayEmotionData(BaseModel):
    unavailableReason: str | None = None
    positive_current: float | None = None
    negative_current: float | None = None
    index_current: float | None = None
    points: list[IntradayEmotionPoint] = Field(default_factory=list)


class ShortEmotionPoint(BaseModel):
    time: str
    value: float
    turnover: float | None = None


class ShortEmotionDay(BaseModel):
    date: str
    points: list[ShortEmotionPoint] = Field(default_factory=list)


class ShortEmotionData(BaseModel):
    unavailableReason: str | None = None
    days: list[ShortEmotionDay] = Field(default_factory=list)
    latest_value: float | None = None
    latest_turnover: float | None = None
    zone: str


class TopicStockItem(BaseModel):
    name: str
    code: str
    reason: str
    concepts: list[str] | None = None
    lbc: int | None = None
    time: int | None = None
    type: str
    fund: int | None = None
    price: float | None = None
    turnoverRate: float | None = None
    zbc: int | None = None
    firstBreak: int | None = None
    lastSealTs: int | None = None


class TopicPoolData(BaseModel):
    date: str
    items: list[TopicStockItem] = Field(default_factory=list)


class PoolsBatchRequest(BaseModel):
    dates: list[str] = Field(default_factory=list)
    kinds: list[str] | None = None


class PoolsBatchData(BaseModel):
    ztByDate: dict[str, list[TopicStockItem]] = Field(default_factory=dict)
    zbByDate: dict[str, list[TopicStockItem]] = Field(default_factory=dict)
    dtByDate: dict[str, list[TopicStockItem]] = Field(default_factory=dict)


class PlateFlowItem(BaseModel):
    code: str
    name: str
    change: float | None = None
    netFlow: float | None = None
    ztCount: int | None = None
    upCount: int | None = None
    downCount: int | None = None
    flatCount: int | None = None


class PlateUniverseData(BaseModel):
    date: str | None = None
    items: list[PlateFlowItem] = Field(default_factory=list)


class SurgeLimitItem(BaseModel):
    code: str
    name: str
    plates: list[str] = Field(default_factory=list)
    analysis: str | None = None


class SurgeData(BaseModel):
    date: str | None = None
    items: list[SurgeLimitItem] = Field(default_factory=list)


class LatestMarketContextData(BaseModel):
    latestDay: str
    pools: PoolsBatchData
    latestZt: list[TopicStockItem] = Field(default_factory=list)
    latestZb: list[TopicStockItem] = Field(default_factory=list)
    latestDt: list[TopicStockItem] = Field(default_factory=list)
    surge: list[SurgeLimitItem] = Field(default_factory=list)
    conceptIndex: dict[str, list[str]] = Field(default_factory=dict)
    baseUniverse: list[PlateFlowItem] = Field(default_factory=list)
    trendUniverse: list[PlateFlowItem] = Field(default_factory=list)


class QuoteItem(BaseModel):
    name: str
    price: float | None = None
    change: float | None = None


class QuotesData(BaseModel):
    items: dict[str, QuoteItem] = Field(default_factory=dict)


class FundflowRow(BaseModel):
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


class FundflowData(BaseModel):
    items: dict[str, list[FundflowRow]] = Field(default_factory=dict)


class TrendingPlateItem(BaseModel):
    plateId: str | None = None
    name: str | None = None
    description: str | None = None
    stocks: list[dict] = Field(default_factory=list)


class TrendingData(BaseModel):
    items: list[TrendingPlateItem] = Field(default_factory=list)


class PlateMemberItem(BaseModel):
    code: str
    name: str
    price: float | None = None
    change: float | None = None
    amount: float | None = None
    netFlow: float | None = None
    turnoverRate: float | None = None


class PlateMembersData(BaseModel):
    items: list[PlateMemberItem] = Field(default_factory=list)


class PlateIndexItem(BaseModel):
    date: str
    open: float
    close: float
    high: float
    low: float


class PlateIndexData(BaseModel):
    items: list[PlateIndexItem] = Field(default_factory=list)


class PayoffItem(BaseModel):
    rank: int | None = None
    method: str | None = None
    name: str
    change: float | None = None
    plate: str | None = None
    days: int | None = None
    boards: int | None = None
    heat: float | None = None
    tag: str | None = None
    maxDrawdown: float | None = None
    industryBlock: str | None = None


class PayoffData(BaseModel):
    items: list[PayoffItem] = Field(default_factory=list)


class TurnoverPoint(BaseModel):
    time: str
    today: float | None = None
    yesterday: float | None = None


class TurnoverData(BaseModel):
    method: str | None = None
    current: float | None = None
    predict: float | None = None
    previous: float | None = None
    change: float | None = None
    points: list[TurnoverPoint] = Field(default_factory=list)


class StrategyData(BaseModel):
    version: str
    private: dict = Field(default_factory=dict)


class EncryptedStrategyData(BaseModel):
    payload: str


class StrategyUpdateRequest(BaseModel):
    version: str | None = None
    private: dict = Field(default_factory=dict)
