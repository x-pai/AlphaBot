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
from app.skills.definitions import ToolSpec, get_mcp_exposable_tool_specs
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


def _is_forwarded_loop_request(request: Request) -> bool:
    return (request.headers.get("X-AlphaBot-Forwarded") or "").strip() == "1"


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


def _python_type_for_param(param: dict[str, Any]) -> Any:
    param_type = param.get("type")
    if param_type == "integer":
        return int
    if param_type == "number":
        return float
    if param_type == "boolean":
        return bool
    return str


def _build_internal_mcp_tool(spec: ToolSpec) -> Callable[..., Any]:
    serializer = _json_result_serializer(spec.name)

    async def _handler(**kwargs: Any) -> str:
        normalized = dict(kwargs)
        for key, param in spec.parameters.items():
            if key not in normalized:
                continue
            if param.get("type") == "integer" and key not in spec.required and normalized[key] == 0:
                normalized[key] = None
        return await serializer(**normalized)

    parameters = []
    annotations: dict[str, Any] = {"return": str}
    for name, param in spec.parameters.items():
        python_type = _python_type_for_param(param)
        if name in spec.required:
            annotations[name] = python_type
            default = inspect._empty
        elif "default" in param:
            annotations[name] = python_type
            default = param["default"]
        else:
            annotations[name] = Optional[python_type]
            default = None
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotations[name],
            )
        )

    _handler.__name__ = spec.name
    _handler.__doc__ = spec.description
    _handler.__annotations__ = annotations
    _handler.__signature__ = inspect.Signature(parameters=parameters, return_annotation=str)
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
    for spec in get_mcp_exposable_tool_specs():
        mcp.tool()(_build_internal_mcp_tool(spec))


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

        if _is_forwarded_loop_request(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Loop detected: forwarded MCP requests are not accepted"},
            )

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
