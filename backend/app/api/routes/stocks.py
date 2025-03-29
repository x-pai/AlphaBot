from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.db.session import get_db
from app.services.stock_service import StockService
from app.schemas.stock import StockInfo, StockPriceHistory
from app.core.config import settings
from app.utils.response import api_response
from app.api.dependencies import check_usage_limit
from app.utils.stock_utils import update_stock_data_with_db

router = APIRouter()

@router.get("/search", response_model=dict)
async def search_stocks(
    q: Optional[str] = Query(None, description="搜索关键词"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """搜索股票"""
    search_term = q
    
    if not search_term:
        return api_response(success=False, error="请提供搜索关键词（使用q或query参数）")
    
    try:
        stocks = await StockService.search_stocks(search_term, data_source, db)
        return api_response(data=stocks)
    except Exception as e:
        return api_response(success=False, error=f"搜索股票失败: {str(e)}")

@router.get("/{symbol}", response_model=dict)
async def get_stock_info(
    symbol: str,
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票详细信息"""
    stock_info = await StockService.get_stock_info(symbol, data_source)
    if not stock_info:
        return api_response(success=False, error="未找到股票信息")

    return api_response(data=stock_info)

@router.get("/{symbol}/history", response_model=dict)
async def get_stock_price_history(
    symbol: str,
    interval: str = Query("daily", description="数据间隔: daily, weekly, monthly"),
    range: str = Query("1m", description="时间范围: 1m, 3m, 6m, 1y, 5y"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票历史价格数据"""
    # 验证参数
    valid_intervals = ["daily", "weekly", "monthly"]
    valid_ranges = ["1m", "3m", "6m", "1y", "5y"]
    
    if interval not in valid_intervals:
        return api_response(success=False, error=f"无效的间隔参数。有效值: {', '.join(valid_intervals)}")
    
    if range not in valid_ranges:
        return api_response(success=False, error=f"无效的时间范围参数。有效值: {', '.join(valid_ranges)}")
    
    price_history = await StockService.get_stock_price_history(symbol, interval, range, data_source)
    if not price_history:
        return api_response(success=False, error="获取股票历史价格失败")
    
    return api_response(data=price_history)

@router.post("/{symbol}/update")
async def update_stock_data(
    symbol: str,
    background_tasks: BackgroundTasks,
    _: None = Depends(check_usage_limit)
):
    """手动更新特定股票数据"""
    background_tasks.add_task(update_stock_data_with_db, symbol)
    return api_response(data={"message": f"开始更新股票 {symbol} 的数据"})

@router.post("/update-all")
async def update_all_stocks(
    background_tasks: BackgroundTasks,
    _: None = Depends(check_usage_limit)
):
    """手动更新所有股票数据"""
    background_tasks.add_task(update_stock_data_with_db)
    return api_response(data={"message": "开始更新所有股票数据"})

@router.get("/{symbol}/intraday", response_model=dict)
async def get_stock_intraday(
    symbol: str,
    refresh: bool = Query(False, description="强制刷新数据，不使用缓存"),
    data_source: Optional[str] = Query(None, description="数据源: alphavantage, tushare, akshare"),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    """获取股票分时数据"""
    try:
        intraday_data = await StockService.get_stock_intraday(symbol, refresh, data_source)
        if not intraday_data:
            return api_response(success=False, error=f"未找到股票 {symbol} 的分时数据")
            
        return api_response(data=intraday_data)
    except Exception as e:
        return api_response(success=False, error=f"获取分时数据时出错: {str(e)}")