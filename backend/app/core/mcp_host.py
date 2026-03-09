from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
import yaml
from fastmcp import Client
import mcp

from app.middleware.logging import logger


@dataclass
class McpServer:
    """MCP Server 描述：当前仅支持 HTTP JSON-RPC 传输。"""

    id: str
    base_url: str
    api_key: Optional[str] = None


class McpHostRegistry:
    """
    AlphaBot 作为 MCP 宿主的注册表。

    - 通过 YAML 配置加载多个 MCP HTTP Server
    - 通过 list_tools 自动发现工具（使用 FastMCP 官方 Client）
    - 为 Agent 提供工具查询接口，供动态挂载为 Tool/Skill 使用

    注意：对外暴露给 LLM 的工具名需要满足 DeepSeek 等模型的正则限制
    `^[a-zA-Z0-9_-]+$`，因此这里会为每个外部 MCP 工具生成一个
    “LLM 安全”的别名，并维护从别名到真实 full_name（server_id.tool）的映射。
    """

    _servers: Dict[str, McpServer] = {}
    # key: full_name（server_id.tool_name），value: { server_id, tool, llm_name }
    _tools: Dict[str, Dict[str, Any]] = {}
    # key: llm_name，value: full_name
    _llm_name_to_full: Dict[str, str] = {}
    _initialized: bool = False

    @classmethod
    def load_from_file(cls, path: str = "app/config/mcp_servers.yml") -> None:
        """从 YAML 配置加载 MCP Server 列表。"""
        try:
            if not os.path.exists(path):
                logger.info("MCP servers config not found: %s", path)
                return
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except Exception as e:  # noqa: BLE001
            logger.error("加载 MCP servers 配置失败: %s", e)
            return

        servers_cfg = (raw or {}).get("servers") or []
        servers: Dict[str, McpServer] = {}
        for item in servers_cfg:
            try:
                sid = str(item.get("id") or "").strip()
                base_url = str(item.get("base_url") or "").strip()
                if not sid or not base_url:
                    continue
                # 支持 ${ENV_VAR} 占位符
                base_url = os.path.expandvars(base_url)
                api_key = item.get("api_key")
                if isinstance(api_key, str):
                    api_key = os.path.expandvars(api_key)
                servers[sid] = McpServer(id=sid, base_url=base_url, api_key=api_key)
            except Exception as e:  # noqa: BLE001
                logger.error("解析 MCP server 配置失败: %s", e)

        cls._servers = servers
        cls._initialized = True
        if servers:
            logger.info("MCP Host: loaded %d servers", len(servers))

    @classmethod
    async def discover_tools(cls) -> None:
        """调用每个 MCP Server 的 tools/list，自动发现工具。"""
        if not cls._initialized:
            cls.load_from_file()

        tools: Dict[str, Dict[str, Any]] = {}
        llm_aliases: Dict[str, str] = {}
        for server_id, server in cls._servers.items():
            try:
                server_tools = await cls._list_tools_for_server(server)
                for t in server_tools:
                    name = t.get("name")
                    if not name:
                        continue
                    full_name = f"{server_id}.{name}"
                    llm_name = cls._to_llm_tool_name(full_name, llm_aliases)
                    tools[full_name] = {
                        "server_id": server_id,
                        "tool": t,
                        "llm_name": llm_name,
                    }
                    llm_aliases[llm_name] = full_name
                if server_tools:
                    logger.info(
                        "MCP Host: server %s discovered %d tools",
                        server_id,
                        len(server_tools),
                    )
            except Exception as e:  # noqa: BLE001
                logger.error("MCP Host: list tools for server %s failed: %s", server_id, e)

        cls._tools = tools
        cls._llm_name_to_full = llm_aliases

    @classmethod
    async def _list_tools_for_server(cls, server: McpServer) -> List[Dict[str, Any]]:
        """
        对单个 MCP Server 调用 list_tools（使用 FastMCP 官方 Client）。

        使用 FastMCP 的 Client 自动选择合适的传输方式（包括 HTTP Streamable / SSE），
        避免手写 sessionId / Accept 头等兼容逻辑。
        """
        # 目前仅使用 URL 作为 transport；如需带鉴权，可后续扩展为 MCPConfig
        client = Client(server.base_url)

        async with client:
            mcp_tools: List[mcp.types.Tool] = await client.list_tools()

        tools: List[Dict[str, Any]] = []
        for t in mcp_tools:
            # 将 MCP Tool 模型转换为简单 dict，供 AgentService 使用
            input_schema: Dict[str, Any] = {}
            try:
                if getattr(t, "inputSchema", None) is not None:
                    input_schema = t.inputSchema.model_dump(mode="json")  # type: ignore[assignment]
            except Exception:  # noqa: BLE001
                input_schema = {}

            tools.append(
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": input_schema,
                }
            )

        return tools

    # ----------------- 对外查询接口 -----------------

    @classmethod
    def list_tools(cls) -> Dict[str, Dict[str, Any]]:
        """返回所有已发现的 MCP 工具，key 为 full_name（server.tool）。"""
        return cls._tools

    @classmethod
    def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具定义。

        - 优先按 full_name 查找（server_id.tool）
        - 若未命中，再按 llm_name（供 LLM 工具调用返回的 function.name 使用）
        """
        entry = cls._tools.get(name)
        if entry is not None:
            return entry
        full_name = cls._llm_name_to_full.get(name)
        if full_name:
            return cls._tools.get(full_name)
        return None

    @classmethod
    def get_server(cls, server_id: str) -> Optional[McpServer]:
        return cls._servers.get(server_id)

    # ----------------- 内部工具名规范化 -----------------

    @staticmethod
    def _to_llm_tool_name(full_name: str, existing: Dict[str, str]) -> str:
        """
        将内部 full_name（如 trendradar.get_latest_news）转换为
        LLM 安全的工具名（只包含字母/数字/下划线/中划线）。
        """
        import re

        # 1) 基本替换：点号和其他非法字符 -> 下划线
        base = re.sub(r"[^a-zA-Z0-9_-]", "_", full_name.replace(".", "_"))
        # 2) 不能全空，且最好不要以非字母数字开头
        base = base.lstrip("_-")
        if not base:
            base = "tool"

        # 3) 处理潜在重名：在尾部追加序号
        candidate = base
        idx = 2
        while candidate in existing and existing[candidate] != full_name:
            candidate = f"{base}_{idx}"
            idx += 1

        return candidate

