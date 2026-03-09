"""
Phase 6 T6.0: MCP Server — 将 Agent 工具暴露给 Cursor / Claude Desktop 等 MCP 客户端。
通过环境变量 MCP_USER_ID 指定当前用户 ID，未设置时默认 1。
启动方式（在 backend 目录下）: python -m app.mcp_server  或  uv run --with fastmcp python -m app.mcp_server
"""
import asyncio
import json
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.services.agent_service import AgentService


def _get_mcp_user_id() -> int:
    raw = os.getenv("MCP_USER_ID", "1").strip()
    try:
        return int(raw)
    except ValueError:
        return 1


def _get_db_and_user():
    db = SessionLocal()
    user_id = _get_mcp_user_id()
    user = db.get(User, user_id)
    if not user:
        db.close()
        raise RuntimeError(f"MCP_USER_ID={user_id} 对应用户不存在")
    return db, user


async def _execute(tool_name: str, params: dict) -> dict:
    db, user = _get_db_and_user()
    try:
        result = await AgentService.execute_tool(tool_name, params, db, user)
        return result if isinstance(result, dict) else {"result": result}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MCP 使用官方库 FastMCP（若不可用则退化为占位，需 pip install fastmcp）
# ---------------------------------------------------------------------------
try:
    from fastmcp import FastMCP
    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False
    FastMCP = None


def _build_mcp_app():
    if not _HAS_FASTMCP:
        raise ImportError("请安装 fastmcp: pip install fastmcp")
    mcp = FastMCP("AlphaBot")

    @mcp.tool()
    async def get_my_positions(data_source: str = "") -> str:
        """获取当前用户持仓列表（含盈亏）。"""
        r = await _execute("get_my_positions", {"data_source": data_source})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def get_my_trades(symbol: Optional[str] = None, limit: int = 50) -> str:
        """获取当前用户交易记录。"""
        r = await _execute("get_my_trades", {"symbol": symbol or "", "limit": limit})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def add_trade(
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0,
        confirm_full_sell: bool = False,
    ) -> str:
        """记录一笔交易。side 为 buy 或 sell。"""
        r = await _execute("add_trade", {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "fee": fee,
            "confirm_full_sell": confirm_full_sell,
        })
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def get_portfolio_summary(data_source: str = "") -> str:
        """获取组合汇总（总资产、盈亏等）。"""
        r = await _execute("get_portfolio_summary", {"data_source": data_source})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def set_price_alert(
        symbol: str,
        rule_type: str = "price_change_pct",
        threshold_pct: Optional[float] = None,
        ma_period: int = 20,
        above_below: str = "below",
        volume_multiplier: float = 2,
    ) -> str:
        """设置价格预警。rule_type: price_change_pct / price_vs_ma / volume_spike。"""
        params = {"symbol": symbol, "rule_type": rule_type}
        if rule_type == "price_change_pct" and threshold_pct is not None:
            params["threshold_pct"] = threshold_pct
        elif rule_type == "price_vs_ma":
            params["ma_period"] = ma_period
            params["above_below"] = above_below
        elif rule_type == "volume_spike":
            params["volume_multiplier"] = volume_multiplier
        r = await _execute("set_price_alert", params)
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def list_my_alerts(symbol: Optional[str] = None) -> str:
        """列出当前用户的价格预警规则。"""
        r = await _execute("list_my_alerts", {"symbol": symbol or ""})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def delete_alert(rule_id: int) -> str:
        """删除一条预警规则。"""
        r = await _execute("delete_alert", {"rule_id": rule_id})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def save_investment_note(content: str, tags: str = "") -> str:
        """将投资笔记保存到长期记忆。"""
        r = await _execute("save_investment_note", {"content": content, "tags": tags})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def get_portfolio_health(data_source: str = "") -> str:
        """获取组合体检（集中度、风格等）。"""
        r = await _execute("get_portfolio_health", {"data_source": data_source})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def import_trades(csv: str) -> str:
        """从 CSV 文本导入交易记录。"""
        r = await _execute("import_trades", {"csv": csv})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def search_stocks(query: str, data_source: str = "akshare") -> str:
        """按关键词搜索股票。"""
        r = await _execute("search_stocks", {"query": query, "data_source": data_source})
        return json.dumps(r, ensure_ascii=False, default=str)

    @mcp.tool()
    async def get_stock_info(symbol: str, data_source: str = "akshare") -> str:
        """获取单只股票详情。"""
        r = await _execute("get_stock_info", {"symbol": symbol, "data_source": data_source})
        return json.dumps(r, ensure_ascii=False, default=str)

    return mcp


if __name__ == "__main__":
    app = _build_mcp_app()
    # 默认 streamable-http 便于 MCP Inspector 或 Cursor 连接
    app.run(transport="streamable-http")
