"""
完整版 MCP Server。

- 使用独立 MCP Token 鉴权，但仍复用原有 User 体系
- MCP 访问要求用户积分 >= 200
- MCP 工具调用默认每日 50 次；积分 >= 1000 时不受限制
- 与主 API 共用同一套数据库与业务服务
"""

from __future__ import annotations

import inspect
import json
import os
from contextvars import ContextVar
from typing import Any, Callable, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import mcp.types as mt

from app.db.session import SessionLocal
from app.models.user import User
from app.services.agent_service import AgentService
from app.core.mcp_host import McpHostRegistry
from app.services.mcp_token_service import McpTokenService
from app.services.usage_service import UsageService

try:
    from fastmcp import FastMCP
    from fastmcp.exceptions import ToolError
    from fastmcp.server.middleware import Middleware, MiddlewareContext
    from fastmcp.server.providers.proxy import ProxyProvider

    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False
    FastMCP = None
    ToolError = None
    Middleware = None
    MiddlewareContext = None
    ProxyProvider = None


_CURRENT_MCP_USER_ID: ContextVar[Optional[int]] = ContextVar("mcp_user_id", default=None)


def _get_authenticated_user_id() -> int:
    user_id = _CURRENT_MCP_USER_ID.get()
    if user_id is None:
        raise RuntimeError("MCP request is not authenticated")
    return user_id


def _extract_bearer_token(request: Request) -> str:
    auth_header = (request.headers.get("authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return token


async def _execute_authenticated(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        user_id = _get_authenticated_user_id()
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        result = await AgentService.execute_tool(tool_name, params, db, user)
        return result if isinstance(result, dict) else {"result": result}
    except HTTPException as exc:
        return {"error": exc.detail}
    finally:
        db.close()


def _json_result_serializer(tool_name: str) -> Callable[..., Any]:
    async def _handler(**kwargs: Any) -> str:
        result = await _execute_authenticated(tool_name, kwargs)
        return json.dumps(result, ensure_ascii=False, default=str)

    _handler.__name__ = tool_name
    return _handler


if _HAS_FASTMCP:
    class McpUsageMiddleware(Middleware):
        """统一在 MCP tools/call 层执行额度检查，避免内部/外部工具计费不一致。"""

        async def on_call_tool(
            self,
            context: MiddlewareContext[mt.CallToolRequestParams],
            call_next: Callable[[MiddlewareContext[mt.CallToolRequestParams]], Any],
        ) -> Any:
            db = SessionLocal()
            try:
                user_id = _get_authenticated_user_id()
                user = db.get(User, user_id)
                if not user:
                    raise ToolError("User not found")
                try:
                    UsageService.require_mcp_usage(user, db)
                except HTTPException as exc:
                    raise ToolError(str(exc.detail)) from exc
            finally:
                db.close()
            return await call_next(context)


def _initialize_external_mcp_tools() -> None:
    try:
        McpHostRegistry.load_from_file()
    except Exception:
        # 不阻断 MCP 服务启动，保留内部工具
        pass


def _register_tools(mcp) -> None:
    @mcp.tool()
    async def get_my_positions(data_source: str = "") -> str:
        """获取当前用户持仓列表（含盈亏）。"""
        return await _json_result_serializer("get_my_positions")(data_source=data_source)

    @mcp.tool()
    async def get_my_trades(symbol: Optional[str] = None, limit: int = 50) -> str:
        """获取当前用户交易记录。"""
        return await _json_result_serializer("get_my_trades")(symbol=symbol or "", limit=limit)

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
        return await _json_result_serializer("add_trade")(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            confirm_full_sell=confirm_full_sell,
        )

    @mcp.tool()
    async def get_portfolio_summary(data_source: str = "") -> str:
        """获取组合汇总（总资产、盈亏等）。"""
        return await _json_result_serializer("get_portfolio_summary")(data_source=data_source)

    @mcp.tool()
    async def set_price_alert(
        symbol: str,
        rule_type: str = "price_change_pct",
        threshold_pct: Optional[float] = None,
        ma_period: int = 20,
        above_below: str = "below",
        volume_multiplier: float = 2,
    ) -> str:
        """设置价格预警。"""
        params: dict[str, Any] = {"symbol": symbol, "rule_type": rule_type}
        if rule_type == "price_change_pct" and threshold_pct is not None:
            params["threshold_pct"] = threshold_pct
        elif rule_type == "price_vs_ma":
            params["ma_period"] = ma_period
            params["above_below"] = above_below
        elif rule_type == "volume_spike":
            params["volume_multiplier"] = volume_multiplier
        return await _json_result_serializer("set_price_alert")(**params)

    @mcp.tool()
    async def list_my_alerts(symbol: Optional[str] = None) -> str:
        """列出当前用户的价格预警规则。"""
        return await _json_result_serializer("list_my_alerts")(symbol=symbol or "")

    @mcp.tool()
    async def delete_alert(rule_id: int) -> str:
        """删除一条预警规则。"""
        return await _json_result_serializer("delete_alert")(rule_id=rule_id)

    @mcp.tool()
    async def save_investment_note(content: str, tags: str = "") -> str:
        """将投资笔记保存到长期记忆。"""
        return await _json_result_serializer("save_investment_note")(content=content, tags=tags)

    @mcp.tool()
    async def get_portfolio_health(data_source: str = "") -> str:
        """获取组合体检。"""
        return await _json_result_serializer("get_portfolio_health")(data_source=data_source)

    @mcp.tool()
    async def import_trades(csv: str) -> str:
        """从 CSV 文本导入交易记录。"""
        return await _json_result_serializer("import_trades")(csv=csv)

    @mcp.tool()
    async def search_stocks(query: str, data_source: str = "akshare") -> str:
        """按关键词搜索股票。"""
        return await _json_result_serializer("search_stocks")(query=query, data_source=data_source)

    @mcp.tool()
    async def get_stock_info(symbol: str, data_source: str = "akshare") -> str:
        """获取单只股票详情。"""
        return await _json_result_serializer("get_stock_info")(symbol=symbol, data_source=data_source)

    @mcp.tool()
    async def get_stock_price_history(
        symbol: str,
        interval: str = "daily",
        range: str = "1m",
        data_source: str = "akshare",
    ) -> str:
        """获取股票历史价格数据。"""
        return await _json_result_serializer("get_stock_price_history")(
            symbol=symbol,
            interval=interval,
            range=range,
            data_source=data_source,
        )

    @mcp.tool()
    async def get_market_news(symbol: str, limit: int = 5, data_source: str = "akshare") -> str:
        """获取市场新闻和公告。"""
        return await _json_result_serializer("get_market_news")(
            symbol=symbol,
            limit=limit,
            data_source=data_source,
        )

    @mcp.tool()
    async def get_stock_fundamentals(
        symbol: str,
        report_type: str = "all",
        data_source: str = "akshare",
    ) -> str:
        """获取股票基本面数据。"""
        return await _json_result_serializer("get_stock_fundamentals")(
            symbol=symbol,
            report_type=report_type,
            data_source=data_source,
        )

    @mcp.tool()
    async def run_backtest(
        symbol: str,
        start_date: str,
        end_date: str,
        data_source: str = "akshare",
    ) -> str:
        """运行回测。"""
        return await _json_result_serializer("run_backtest")(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
        )

    @mcp.tool()
    async def get_sim_positions() -> str:
        """获取模拟仓位。"""
        return await _json_result_serializer("get_sim_positions")()

    @mcp.tool()
    async def add_sim_trade(
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> str:
        """记录模拟交易。"""
        return await _json_result_serializer("add_sim_trade")(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )

    @mcp.tool()
    async def search_web(query: str, limit: int = 5) -> str:
        """联网搜索，要求用户积分至少 2000。"""
        return await _json_result_serializer("search_web")(query=query, limit=limit)


def _register_external_mcp_tools(mcp) -> None:
    for server in McpHostRegistry.list_servers().values():
        if not server.enabled:
            continue
        try:
            mcp.add_provider(
                ProxyProvider(lambda server=server: McpHostRegistry._build_client(server)),
                namespace=server.id,
            )
        except Exception:
            # 若外部服务注册失败，不阻断整个 MCP 服务
            continue


def _build_mcp_app():
    if not _HAS_FASTMCP:
        raise ImportError("请安装 fastmcp: pip install fastmcp")
    _initialize_external_mcp_tools()
    mcp = FastMCP("AlphaBot")
    mcp.add_middleware(McpUsageMiddleware())
    _register_tools(mcp)
    _register_external_mcp_tools(mcp)
    return mcp


def _build_fastmcp_http_app(mcp) -> Any:
    candidates = [
        ("http_app", [{}, {"path": "/mcp"}, {"path": "/"}]),
        ("streamable_http_app", [{}, {"path": "/mcp"}, {"path": "/"}]),
        ("sse_app", [{}, {"path": "/mcp"}, {"path": "/"}]),
    ]
    for method_name, kwargs_list in candidates:
        method = getattr(mcp, method_name, None)
        if not callable(method):
            continue
        for kwargs in kwargs_list:
            try:
                signature = inspect.signature(method)
                supported_kwargs = {k: v for k, v in kwargs.items() if k in signature.parameters}
                return method(**supported_kwargs)
            except TypeError:
                continue
    raise RuntimeError("当前 fastmcp 版本未暴露可挂载的 HTTP ASGI 应用")


def build_http_app() -> FastAPI:
    if not _HAS_FASTMCP:
        app = FastAPI(title="AlphaBot MCP Server")

        @app.get("/health")
        async def health_check():
            return {"status": "ok"}

        @app.get("/mcp")
        async def missing_dependency():
            return JSONResponse(
                status_code=503,
                content={"detail": "fastmcp is not installed"},
            )

        return app

    mcp = _build_mcp_app()
    asgi_app = _build_fastmcp_http_app(mcp)
    app = FastAPI(title="AlphaBot MCP Server", lifespan=asgi_app.lifespan)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.middleware("http")
    async def mcp_auth_middleware(request: Request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        db = SessionLocal()
        token_ctx = None
        try:
            raw_token = _extract_bearer_token(request)
            mcp_token = McpTokenService.authenticate_token(db, raw_token)
            if not mcp_token.user.can_use_mcp:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "MCP requires at least 200 points"},
                )
            McpTokenService.touch_token(
                db,
                mcp_token,
                client_ip=request.client.host if request.client else None,
            )
            token_ctx = _CURRENT_MCP_USER_ID.set(mcp_token.user_id)
            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        finally:
            if token_ctx is not None:
                _CURRENT_MCP_USER_ID.reset(token_ctx)
            db.close()

    # 不能再 mount("/mcp")，否则 Starlette 会把前缀剥掉，导致 FastMCP
    # 子应用拿到 "/" 而不是它实际监听的 "/mcp"，从而出现 307 后 404。
    # 这里直接挂在根层，让 FastMCP 自己处理 "/mcp" 路径。
    app.mount("/", asgi_app)
    return app


app = build_http_app()


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", "8001"))
    uvicorn.run("app.mcp_server:app", host="0.0.0.0", port=port, reload=False)
