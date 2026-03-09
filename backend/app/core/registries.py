"""
能力标准化扩展（Phase 5）：分析模式、工具、搜索引擎的注册表，配置即切换。
"""

from typing import List, Set

from app.core.config import settings


class AnalysisModeRegistry:
    """分析模式注册表：rule / ml / llm 可配置切换。"""

    AVAILABLE = ("rule", "ml", "llm")

    @classmethod
    def get(cls) -> str:
        mode = (settings.DEFAULT_ANALYSIS_MODE or "rule").strip().lower()
        return mode if mode in cls.AVAILABLE else "rule"

    @classmethod
    def list_modes(cls) -> List[str]:
        return list(cls.AVAILABLE)


class ToolRegistry:
    """Agent 工具注册表：配置启用/禁用工具。"""

    # 所有可配置的工具名（与 AgentService.get_available_tools 中 name 一致）
    ALL_TOOLS: Set[str] = {
        "search_stocks", "get_stock_info", "get_stock_price_history",
        "get_market_news", "get_stock_fundamentals",
        "get_my_positions", "get_my_trades", "add_trade", "get_portfolio_summary",
        "set_price_alert", "list_my_alerts", "delete_alert",
        "save_investment_note", "get_portfolio_health", "import_trades",
        "search_web",
        "run_backtest", "get_sim_positions", "add_sim_trade",
    }

    @classmethod
    def enabled_set(cls) -> Set[str]:
        raw = getattr(settings, "ENABLED_AGENT_TOOLS", None) or ""
        if not raw or not raw.strip():
            return cls.ALL_TOOLS
        return {t.strip() for t in raw.split(",") if t.strip()}

    @classmethod
    def is_enabled(cls, tool_name: str) -> bool:
        return tool_name in cls.enabled_set()


class SearchRegistry:
    """搜索引擎注册表：可配置切换 serpapi / googleapi / bingapi。"""

    AVAILABLE = ("serpapi", "googleapi", "bingapi")

    @classmethod
    def get(cls) -> str:
        engine = (settings.SEARCH_ENGINE or "serpapi").strip().lower()
        return engine if engine in cls.AVAILABLE else "serpapi"

    @classmethod
    def list_engines(cls) -> List[str]:
        return list(cls.AVAILABLE)
