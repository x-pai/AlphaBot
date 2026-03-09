"""
MCP Server 测试（T6.0）

测试 _get_mcp_user_id、_execute 与 Agent 工具的桥接逻辑。
不依赖 fastmcp 包即可运行；若需验证 FastMCP 应用构建，需 pip install fastmcp。
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# 在导入 mcp_server 前可 patch，避免未安装 fastmcp 时 _build_mcp_app 报错
import app.mcp_server as mcp_module


class TestGetMcpUserId:
    """环境变量 MCP_USER_ID"""

    def test_default_is_one(self):
        with patch.dict(os.environ, {}, clear=False):
            if "MCP_USER_ID" in os.environ:
                del os.environ["MCP_USER_ID"]
            assert mcp_module._get_mcp_user_id() == 1

    def test_from_env(self):
        with patch.dict(os.environ, {"MCP_USER_ID": "42"}):
            assert mcp_module._get_mcp_user_id() == 42

    def test_invalid_falls_back_to_one(self):
        with patch.dict(os.environ, {"MCP_USER_ID": "abc"}):
            assert mcp_module._get_mcp_user_id() == 1


@pytest.mark.asyncio
class TestExecuteBridge:
    """_execute 正确调用 AgentService.execute_tool 并返回 JSON 可序列化结果"""

    async def test_execute_get_my_positions(self):
        with patch.object(mcp_module, "_get_db_and_user") as m_get:
            db = MagicMock()
            user = MagicMock()
            user.id = 1
            m_get.return_value = (db, user)
            with patch.object(mcp_module.AgentService, "execute_tool", new_callable=AsyncMock) as m_run:
                m_run.return_value = {"positions": [], "total": 0}
                out = await mcp_module._execute("get_my_positions", {"data_source": "akshare"})
                assert out == {"positions": [], "total": 0}
                m_run.assert_called_once_with("get_my_positions", {"data_source": "akshare"}, db, user)
            db.close.assert_called_once()

    async def test_execute_add_trade(self):
        with patch.object(mcp_module, "_get_db_and_user") as m_get:
            db = MagicMock()
            user = MagicMock()
            user.id = 1
            m_get.return_value = (db, user)
            with patch.object(mcp_module.AgentService, "execute_tool", new_callable=AsyncMock) as m_run:
                m_run.return_value = {"success": True, "message": "已记录"}
                out = await mcp_module._execute("add_trade", {
                    "symbol": "AAPL", "side": "buy", "quantity": 10, "price": 150,
                })
                assert out["success"] is True
                m_run.assert_called_once()
            db.close.assert_called_once()

    async def test_execute_non_dict_wrapped(self):
        with patch.object(mcp_module, "_get_db_and_user") as m_get:
            db = MagicMock()
            user = MagicMock()
            m_get.return_value = (db, user)
            with patch.object(mcp_module.AgentService, "execute_tool", new_callable=AsyncMock) as m_run:
                m_run.return_value = "plain_string"
                out = await mcp_module._execute("list_my_alerts", {})
                assert out == {"result": "plain_string"}
            db.close.assert_called_once()


class TestBuildMcpApp:
    """_build_mcp_app 在 fastmcp 可用时返回 FastMCP 应用"""

    def test_raises_when_fastmcp_not_installed(self):
        with patch.object(mcp_module, "_HAS_FASTMCP", False):
            with pytest.raises(ImportError, match="请安装 fastmcp"):
                mcp_module._build_mcp_app()

    def test_returns_app_when_fastmcp_available(self):
        if not getattr(mcp_module, "_HAS_FASTMCP", False):
            pytest.skip("fastmcp 未安装，跳过 FastMCP 构建测试")
        app = mcp_module._build_mcp_app()
        assert app is not None
        # FastMCP 应用通常有 name 或 _tools
        assert getattr(app, "name", None) == "AlphaBot" or hasattr(app, "_tools") or hasattr(app, "list_tools")
