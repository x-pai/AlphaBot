from typing import Dict, Type

from app.core.config import settings
from app.services.data_sources.base import DataSourceBase
from app.services.data_sources.alpha_vantage import AlphaVantageDataSource
from app.services.data_sources.tushare import TushareDataSource
from app.services.data_sources.akshare import AKShareDataSource

class DataSourceFactory:
    """数据源工厂，用于创建和管理数据源实例"""
    
    # 数据源类映射
    _source_classes: Dict[str, Type[DataSourceBase]] = {
        "alphavantage": AlphaVantageDataSource,
        "tushare": TushareDataSource,
        "akshare": AKShareDataSource
    }
    
    # 数据源实例缓存
    _instances: Dict[str, DataSourceBase] = {}
    
    @classmethod
    def get_data_source(cls, source_name: str = None) -> DataSourceBase:
        """获取数据源实例
        
        Args:
            source_name: 数据源名称，如果为 None，则使用默认数据源
            
        Returns:
            数据源实例
        """
        # 如果未指定数据源，使用默认数据源
        if source_name is None:
            source_name = settings.DEFAULT_DATA_SOURCE
        
        # 如果数据源名称无效，使用默认数据源
        if source_name not in cls._source_classes:
            print(f"警告: 无效的数据源名称 '{source_name}'，使用默认数据源 '{settings.DEFAULT_DATA_SOURCE}'")
            source_name = settings.DEFAULT_DATA_SOURCE
        
        # 如果实例已存在，直接返回
        if source_name in cls._instances:
            return cls._instances[source_name]
        
        # 创建新实例
        source_class = cls._source_classes[source_name]
        instance = source_class()
        
        # 缓存实例
        cls._instances[source_name] = instance
        
        return instance 