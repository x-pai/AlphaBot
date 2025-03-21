from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import pandas as pd

from app.schemas.stock import StockInfo, StockPriceHistory

class DataSourceBase(ABC):
    """数据源基类，定义所有数据源需要实现的接口"""
    
    @abstractmethod
    async def search_stocks(self, query: str) -> List[StockInfo]:
        """搜索股票"""
        pass
    
    @abstractmethod
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """获取股票详细信息"""
        pass
    
    @abstractmethod
    async def get_stock_price_history(
        self, 
        symbol: str, 
        interval: str = "daily", 
        range: str = "1m"
    ) -> Optional[StockPriceHistory]:
        """获取股票历史价格数据"""
        pass
    
    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """获取公司基本面数据"""
        pass
    
    @abstractmethod
    async def get_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取股票历史数据"""
        pass
    
    @abstractmethod
    async def get_news_sentiment(self, symbol: str) -> Dict[str, Any]:
        """获取新闻情绪分析"""
        pass
    
    @abstractmethod
    async def get_sector_linkage(self, symbol: str) -> Dict[str, Any]:
        """获取板块联动性分析"""
        pass
    
    @abstractmethod
    async def get_concept_distribution(self, symbol: str) -> Dict[str, Any]:
        """获取概念涨跌分布分析"""
        pass
        
    @abstractmethod
    async def get_intraday_data(self, symbol: str, refresh: bool = False) -> Dict[str, Any]:
        """获取股票分时数据"""
        pass 