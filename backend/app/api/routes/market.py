from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.routes.user import get_current_admin, get_current_user
from app.schemas.market import (
    ApiEnvelope,
    EncryptedStrategyData,
    FundflowData,
    IntradayEmotionData,
    LatestMarketContextData,
    PayoffData,
    PlateIndexData,
    PlateMembersData,
    PlateUniverseData,
    PoolsBatchData,
    PoolsBatchRequest,
    QuotesData,
    ShortEmotionData,
    StrategyData,
    StrategyUpdateRequest,
    SurgeData,
    TopicPoolData,
    TradingCalendarData,
    TrendingData,
    TurnoverData,
)
from app.services.market_domain_service import MarketDomainService
from app.services.market_emotion_service import MarketEmotionService
from app.services.app_cipher import encrypt_client_payload
from app.services.trading_calendar_service import TradingCalendarService
from app.utils.response import api_response

router = APIRouter(dependencies=[Depends(get_current_user)])

_STRATEGY_CIPHER_AAD = b"alphabot:market-strategy:v1"
_STRATEGY_NOTICE = "策略参数仅供 AlphaBot 正常使用；若认可本项目，欢迎赞助支持持续维护。"


@router.get("/source-info")
async def get_source_info():
    import hashlib
    import json
    from app.services.market_data_sources.factory import MarketDataSourceFactory
    from app.core.config import settings
    bindings = MarketDataSourceFactory.current_bindings()
    tdx = settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower() == "tdxaidata"
    fingerprint = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()[:16]
    return api_response(data={
        "source": settings.DEFAULT_MARKET_DATA_SOURCE,
        "bindings": bindings,
        "cacheNamespace": f"market-v4-{fingerprint}",
        "notice": ("通达信数据；异动、趋势、强势股及成交额预测按本地规则计算。"
                   "为控制调用成本，人气榜及历史股票池/历史榜单自动回补已暂停，依赖历史的分析暂不可用。实时候选详情最多查询 100 只，超限明确报错。未提供原情绪指标和编辑催化文本。") if tdx else None,
        "unavailable": ["emotion_intraday", "emotion_short", "editorial_catalysts", "payoff_hot", "historical_pools", "historical_payoff"] if tdx else [],
    })


@router.get("/trading-calendar", response_model=ApiEnvelope[TradingCalendarData])
async def get_trading_calendar(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int | None = Query(None, ge=1, le=365),
):
    calendar = await TradingCalendarService.get_trade_calendar()
    values = calendar
    if end_date is not None:
        values = [day for day in values if day <= end_date]
    if start_date is not None:
        values = [day for day in values if day >= start_date]
    if limit is not None:
        values = values[-limit:]

    latest = values[-1].isoformat() if values else None
    return api_response(
        data={
            "days": [day.isoformat() for day in values],
            "latest_trading_day": latest,
        }
    )


@router.get("/emotion/intraday", response_model=ApiEnvelope[IntradayEmotionData])
async def get_intraday_emotion():
    return api_response(data=await MarketEmotionService.get_intraday_emotion())


@router.get("/emotion/short", response_model=ApiEnvelope[ShortEmotionData])
async def get_short_emotion(days: int = Query(5, ge=1, le=20)):
    return api_response(data=await MarketEmotionService.get_short_emotion(days))


@router.get("/pool/{kind}", response_model=ApiEnvelope[TopicPoolData])
async def get_pool(kind: str, date: str | None = Query(None)):
    try:
        return api_response(data=await MarketDomainService.get_pool(kind, date))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/pools/batch", response_model=ApiEnvelope[PoolsBatchData])
async def get_pools_batch(payload: PoolsBatchRequest):
    try:
        return api_response(data=await MarketDomainService.get_pools_batch(payload.dates, payload.kinds))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/universe", response_model=ApiEnvelope[PlateUniverseData])
async def get_universe():
    return api_response(data=await MarketDomainService.get_universe())


@router.get("/surge", response_model=ApiEnvelope[SurgeData])
async def get_surge():
    return api_response(data=await MarketDomainService.get_surge())


@router.get("/context/latest", response_model=ApiEnvelope[LatestMarketContextData])
async def get_latest_context():
    return api_response(data=await MarketDomainService.get_latest_context())


@router.get("/quotes", response_model=ApiEnvelope[QuotesData])
async def get_quotes(symbols: str = Query(..., description="逗号分隔的 6 位代码")):
    return api_response(data=await MarketDomainService.get_quotes(symbols))


@router.get("/fundflow", response_model=ApiEnvelope[FundflowData])
async def get_fundflow(codes: str = Query(..., description="逗号分隔的 6 位代码"), days: int = Query(10, ge=1, le=10)):
    return api_response(data=await MarketDomainService.get_fundflow(codes, days))


@router.get("/trending", response_model=ApiEnvelope[TrendingData])
async def get_trending():
    return api_response(data=await MarketDomainService.get_trending())


@router.get("/plate-members", response_model=ApiEnvelope[PlateMembersData])
async def get_plate_members(plateId: str = Query(...)):
    return api_response(data=await MarketDomainService.get_plate_members(plateId))


@router.get("/plate-index", response_model=ApiEnvelope[PlateIndexData])
async def get_plate_index(plateId: str = Query(...), count: int = Query(12, ge=1, le=60)):
    return api_response(data=await MarketDomainService.get_plate_index(plateId, count))


@router.get("/payoff/{kind}", response_model=ApiEnvelope[PayoffData])
async def get_payoff(kind: str, date: str | None = Query(None)):
    try:
        return api_response(data=await MarketDomainService.get_payoff(kind, date))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/turnover", response_model=ApiEnvelope[TurnoverData])
async def get_turnover():
    return api_response(data=await MarketDomainService.get_turnover())


@router.get("/strategy", response_model=ApiEnvelope[EncryptedStrategyData])
async def get_strategy():
    strategy = await MarketDomainService.get_strategy()
    return api_response(
        data=encrypt_client_payload(
            {"version": strategy.get("version"), "private": strategy.get("private", {}), "notice": _STRATEGY_NOTICE},
            aad=_STRATEGY_CIPHER_AAD,
        )
    )


@router.put("/strategy", response_model=ApiEnvelope[StrategyData])
async def put_strategy(
    payload: StrategyUpdateRequest,
    _current_user=Depends(get_current_admin),
):
    return api_response(data=await MarketDomainService.set_strategy(payload.private, payload.version))
