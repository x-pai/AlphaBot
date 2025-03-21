from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.services.ai_service import AIService
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit

router = APIRouter()

@router.get("/analyze", response_model=dict)
async def analyze_stock(
    symbol: str = Query(..., description="股票代码"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    analysis_type: Optional[str] = Query(None, description="分析类型: rule, ml, llm"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票的 AI 分析"""  
    analysis = await AIService.analyze_stock(symbol, data_source, analysis_type)
    
    if not analysis:
        return api_response(success=False, error="无法生成股票分析")
    
    return api_response(data=analysis)

@router.get("/time-series", response_model=dict)
async def analyze_time_series(
    symbol: str = Query(..., description="股票代码"),
    interval: str = Query("daily", description="数据间隔: daily, weekly, monthly"),
    range: str = Query("1m", description="时间范围: 1m, 3m, 6m, 1y, 5y"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    analysis_type: Optional[str] = Query(None, description="分析类型: rule, ml, llm"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票分时数据的 AI 分析和预测"""
    analysis = await AIService.analyze_time_series(symbol, interval, range, data_source, analysis_type)
    
    if not analysis:
        return api_response(success=False, error="无法生成分时数据分析")
    
    return api_response(data=analysis)

@router.get("/intraday-analysis/{symbol}", response_model=dict)
async def analyze_intraday(
    symbol: str,
    analysis_type: Optional[str] = Query("llm", description="分析类型: rule, ml, llm"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票分时数据的 AI 分析"""
    analysis = await AIService.analyze_intraday(symbol, data_source, analysis_type)
    
    if not analysis:
        return api_response(success=False, error="无法生成分时数据分析")
    
    return api_response(data=analysis) 