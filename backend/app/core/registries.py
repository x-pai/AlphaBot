"""
能力标准化扩展（Phase 5）：分析模式、工具、搜索引擎的注册表，配置即切换。
"""

from typing import List, Set

from app.core.config import settings
from app.skills.definitions import get_internal_tool_names


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

    @classmethod
    def enabled_set(cls) -> Set[str]:
        raw = getattr(settings, "ENABLED_AGENT_TOOLS", None) or ""
        if not raw or not raw.strip():
            return set(get_internal_tool_names())
        return {t.strip() for t in raw.split(",") if t.strip()}

    @classmethod
    def is_enabled(cls, tool_name: str) -> bool:
        all_tools = set(get_internal_tool_names())
        # 对于未在 ALL_TOOLS 中声明的动态工具（例如 MCP 自动发现的工具），
        # 若未显式配置白名单，则默认视为启用。
        if tool_name not in all_tools:
            return True
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
