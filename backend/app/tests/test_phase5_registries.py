"""
Phase 5 能力标准化扩展 测试

ROADMAP: T5.1 AnalysisModeRegistry | T5.2 ToolRegistry | T5.3 SearchRegistry
验收：rule/ml/llm 可配置切换；工具启用/禁用；搜索引擎可配置切换。
"""
import pytest
from unittest.mock import patch

from app.core.config import settings
from app.core.registries import AnalysisModeRegistry, ToolRegistry, SearchRegistry


class TestAnalysisModeRegistry:
    """T5.1 分析模式可配置"""

    def test_get_default(self):
        with patch.object(settings, "DEFAULT_ANALYSIS_MODE", "rule"):
            assert AnalysisModeRegistry.get() == "rule"

    def test_get_ml(self):
        with patch.object(settings, "DEFAULT_ANALYSIS_MODE", "ml"):
            assert AnalysisModeRegistry.get() == "ml"

    def test_get_invalid_falls_back_to_rule(self):
        with patch.object(settings, "DEFAULT_ANALYSIS_MODE", "invalid"):
            assert AnalysisModeRegistry.get() == "rule"

    def test_list_modes(self):
        assert AnalysisModeRegistry.list_modes() == ["rule", "ml", "llm"]


class TestToolRegistry:
    """T5.2 工具启用/禁用"""

    def test_enabled_set_default_all(self):
        with patch.object(settings, "ENABLED_AGENT_TOOLS", ""):
            s = ToolRegistry.enabled_set()
            assert "get_my_positions" in s
            assert "add_trade" in s
            assert "import_trades" in s

    def test_is_enabled_when_whitelist_empty(self):
        with patch.object(settings, "ENABLED_AGENT_TOOLS", ""):
            assert ToolRegistry.is_enabled("get_my_positions") is True
            assert ToolRegistry.is_enabled("add_trade") is True

    def test_is_enabled_respects_whitelist(self):
        with patch.object(settings, "ENABLED_AGENT_TOOLS", "get_my_positions,add_trade"):
            assert ToolRegistry.is_enabled("get_my_positions") is True
            assert ToolRegistry.is_enabled("add_trade") is True
            assert ToolRegistry.is_enabled("search_web") is False


class TestSearchRegistry:
    """T5.3 搜索引擎可配置"""

    def test_get_default(self):
        with patch.object(settings, "SEARCH_ENGINE", "serpapi"):
            assert SearchRegistry.get() == "serpapi"

    def test_get_google(self):
        with patch.object(settings, "SEARCH_ENGINE", "googleapi"):
            assert SearchRegistry.get() == "googleapi"

    def test_list_engines(self):
        assert "serpapi" in SearchRegistry.list_engines()
        assert "bingapi" in SearchRegistry.list_engines()
