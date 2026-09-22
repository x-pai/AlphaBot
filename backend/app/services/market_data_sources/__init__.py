"""市场数据源包：DataSourceFactory + 按领域契约的多源实现。"""

from app.services.market_data_sources.base import MarketDataSourceBase
from app.services.market_data_sources.eastmoney import EastmoneyMarketDataSource
from app.services.market_data_sources.factory import MarketDataSourceFactory
from app.services.market_data_sources.ths import ThsMarketDataSource
from app.services.market_data_sources.tdxaidata import TdxAiDataMarketDataSource
from app.services.market_data_sources.xgb import XgbMarketDataSource

__all__ = [
    "MarketDataSourceBase",
    "MarketDataSourceFactory",
    "XgbMarketDataSource",
    "EastmoneyMarketDataSource",
    "ThsMarketDataSource",
    "TdxAiDataMarketDataSource",
]
