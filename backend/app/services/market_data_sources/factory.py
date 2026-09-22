"""市场数据源工厂：tdxaidata 全量切换；旧来源保留原有按数据集配置。"""

from __future__ import annotations

import json
from typing import Dict, Type

from app.core.config import settings
from app.services.market_data_sources.base import MarketDataSourceBase
from app.services.market_data_sources.eastmoney import EastmoneyMarketDataSource
from app.services.market_data_sources.ths import ThsMarketDataSource
from app.services.market_data_sources.tdxaidata import TdxAiDataMarketDataSource
from app.services.market_data_sources.xgb import XgbMarketDataSource


class MarketDataSourceConfigurationError(ValueError):
    """市场数据源配置未知或不支持所绑定的数据集。"""


class MarketDataSourceFactory:
    """tdxaidata 严格全量切换；其他默认来源保留历史配置兼容。"""

    _source_classes: Dict[str, Type[MarketDataSourceBase]] = {
        "xgb": XgbMarketDataSource,
        "eastmoney": EastmoneyMarketDataSource,
        "ths": ThsMarketDataSource,
        "tdxaidata": TdxAiDataMarketDataSource,
    }
    _instances: Dict[str, MarketDataSourceBase] = {}

    # 无配置时保留项目当前的来源选择。
    _legacy_bindings: Dict[str, str] = {
        "pools": "xgb",
        "universe": "xgb",
        "surge": "xgb",
        "quotes": "xgb",
        "fundflow": "xgb",
        "trending": "xgb",
        "members": "xgb",
        "plate_index": "xgb",
        "payoff_strong": "xgb",
        "turnover": "ths",
        "payoff_hot": "ths",
        "payoff_drawdown": "ths",
    }
    _explicit_bindings: Dict[str, str] = {}

    @classmethod
    def _validate_source_name(cls, source_name: str, setting_name: str) -> None:
        if source_name not in cls._source_classes:
            valid = ", ".join(sorted(cls._source_classes))
            raise MarketDataSourceConfigurationError(
                f"{setting_name}={source_name!r} is unknown; expected one of: {valid}"
            )

    @classmethod
    def _resolve_name(cls, dataset: str) -> str:
        if dataset not in cls._legacy_bindings:
            raise MarketDataSourceConfigurationError(f"unknown market dataset: {dataset}")

        default_name = settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower()
        cls._validate_source_name(default_name, "DEFAULT_MARKET_DATA_SOURCE")

        if default_name == "tdxaidata":
            if any(name != "tdxaidata" for name in cls._explicit_bindings.values()):
                raise MarketDataSourceConfigurationError(
                    "DEFAULT_MARKET_DATA_SOURCE=tdxaidata requires all bindings to use tdxaidata"
                )
            if dataset not in cls._source_classes[default_name].SUPPORTED_DATASETS:
                raise MarketDataSourceConfigurationError(f"tdxaidata does not support {dataset}")
            return default_name

        if dataset in cls._explicit_bindings:
            source_name = cls._explicit_bindings[dataset]
            source_class = cls._source_classes[source_name]
            if dataset not in source_class.SUPPORTED_DATASETS:
                raise MarketDataSourceConfigurationError(
                    f"market dataset {dataset!r} is not supported by explicitly bound source {source_name!r}"
                )
            return source_name

        default_class = cls._source_classes[default_name]
        if dataset in default_class.SUPPORTED_DATASETS:
            return default_name
        return cls._legacy_bindings[dataset]

    @classmethod
    def resolve(cls, dataset: str) -> tuple[str, MarketDataSourceBase]:
        """原子地取得有效来源名和实例，供一次请求固定使用。"""
        source_name = cls._resolve_name(dataset)
        if source_name not in cls._instances:
            cls._instances[source_name] = cls._source_classes[source_name]()
        return source_name, cls._instances[source_name]

    @classmethod
    def get_data_source(cls, dataset: str) -> MarketDataSourceBase:
        """获取数据集当前来源实例。"""
        return cls.resolve(dataset)[1]

    @classmethod
    def reconfigure(cls, bindings: Dict[str, str]) -> None:
        """完整校验后原子应用显式绑定；非法项不会造成部分更新。"""
        if not isinstance(bindings, dict):
            raise MarketDataSourceConfigurationError("MARKET_DATA_BINDINGS must be a JSON object")

        validated: Dict[str, str] = {}
        for dataset, source_name in bindings.items():
            if dataset not in cls._legacy_bindings:
                raise MarketDataSourceConfigurationError(f"unknown market dataset in bindings: {dataset!r}")
            if not isinstance(source_name, str):
                raise MarketDataSourceConfigurationError(f"source for {dataset!r} must be a string")
            source_name = source_name.strip().lower()
            cls._validate_source_name(source_name, f"MARKET_DATA_BINDINGS[{dataset!r}]")
            if dataset not in cls._source_classes[source_name].SUPPORTED_DATASETS:
                raise MarketDataSourceConfigurationError(
                    f"market dataset {dataset!r} is not supported by source {source_name!r}"
                )
            validated[dataset] = source_name

        if settings.DEFAULT_MARKET_DATA_SOURCE.strip().lower() == "tdxaidata" and any(
            name != "tdxaidata" for name in validated.values()
        ):
            raise MarketDataSourceConfigurationError("tdxaidata full switch forbids mixed source bindings")
        cls._explicit_bindings = validated

    @classmethod
    def current_bindings(cls) -> Dict[str, str]:
        """返回所有数据集当前实际解析到的来源。"""
        return {dataset: cls._resolve_name(dataset) for dataset in cls._legacy_bindings}

    @classmethod
    async def aclose(cls) -> None:
        """释放具备异步关闭接口的数据源资源。"""
        for source_name, instance in tuple(cls._instances.items()):
            close = getattr(instance, "aclose", None)
            if close is not None:
                await close()
                cls._instances.pop(source_name, None)


def _load_bindings_from_settings() -> None:
    raw = settings.MARKET_DATA_BINDINGS
    if not raw:
        return
    try:
        bindings = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MarketDataSourceConfigurationError("MARKET_DATA_BINDINGS must contain valid JSON") from exc
    MarketDataSourceFactory.reconfigure(bindings)


_load_bindings_from_settings()
MarketDataSourceFactory.current_bindings()
