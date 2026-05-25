from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ToolHandler = Callable[..., Any]


@dataclass
class ToolSpec:
    name: str
    category: str
    description: str
    parameters: Dict[str, Dict[str, Any]]
    required: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    requires_auth: bool = False
    account_scoped: bool = False
    mcp_exposable: bool = True
    handler: Optional[ToolHandler] = None

    def to_agent_parameters(self) -> Dict[str, Any]:
        return self.parameters


def _spec(
    *,
    name: str,
    category: str,
    description: str,
    parameters: Dict[str, Dict[str, Any]],
    required: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    requires_auth: bool = False,
    account_scoped: bool = False,
    mcp_exposable: bool = True,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        category=category,
        description=description,
        parameters=parameters,
        required=required or [],
        roles=roles or [],
        requires_auth=requires_auth,
        account_scoped=account_scoped,
        mcp_exposable=mcp_exposable,
    )


ROLE_GENERAL = "general"
ROLE_PORTFOLIO = "portfolio"
ROLE_ALERT = "alert"
ROLE_RESEARCH = "research"
ROLE_RISK = "risk"

ALL_ROLES = [ROLE_GENERAL, ROLE_PORTFOLIO, ROLE_ALERT, ROLE_RESEARCH, ROLE_RISK]


INTERNAL_TOOL_SPECS: Dict[str, ToolSpec] = {
    "search_stocks": _spec(
        name="search_stocks",
        category="research",
        description="搜索股票信息，通过关键词查找股票",
        parameters={
            "query": {"type": "string", "description": "搜索关键词，可以是股票名称、代码或行业"},
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        required=["query"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_stock_info": _spec(
        name="get_stock_info",
        category="research",
        description="获取股票的详细信息",
        parameters={
            "symbol": {"type": "string", "description": "股票代码（根据search_stocks工具获取）"},
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        required=["symbol"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_stock_price_history": _spec(
        name="get_stock_price_history",
        category="research",
        description="获取股票历史价格数据",
        parameters={
            "symbol": {"type": "string", "description": "股票代码（根据search_stocks工具获取）"},
            "interval": {
                "type": "string",
                "description": "时间间隔：daily, weekly, monthly",
                "enum": ["daily", "weekly", "monthly"],
            },
            "range": {
                "type": "string",
                "description": "时间范围：1m, 3m, 6m, 1y, 5y",
                "enum": ["1m", "3m", "6m", "1y", "5y"],
            },
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        required=["symbol"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_stock_intraday": _spec(
        name="get_stock_intraday",
        category="research",
        description="获取股票分时数据",
        parameters={
            "symbol": {"type": "string", "description": "股票代码（根据search_stocks工具获取）"},
            "refresh": {"type": "boolean", "description": "是否强制刷新数据，不使用缓存", "default": False},
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock", "tdx"],
            },
        },
        required=["symbol"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_market_news": _spec(
        name="get_market_news",
        category="research",
        description="获取市场新闻和公告",
        parameters={
            "symbol": {"type": "string", "description": "相关股票代码，可选（根据search_stocks工具获取）"},
            "limit": {"type": "integer", "description": "返回新闻条数，默认5条", "default": 5},
            "data_source": {"type": "string", "description": "行情数据源，可选"},
        },
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_stock_fundamentals": _spec(
        name="get_stock_fundamentals",
        category="research",
        description="获取股票的基本面数据，包括财务数据、估值指标等",
        parameters={
            "symbol": {"type": "string", "description": "股票代码（根据search_stocks工具获取）"},
            "report_type": {
                "type": "string",
                "description": "报表类型，all为所有数据",
                "enum": ["all", "balance_sheet", "income", "cash_flow", "performance", "key_metrics"],
            },
            "data_source": {
                "type": "string",
                "description": "数据源：tushare, 默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage"],
            },
        },
        required=["symbol"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "get_my_positions": _spec(
        name="get_my_positions",
        category="account",
        description="获取当前用户的持仓列表，含当前价与浮盈浮亏。涉及「我的持仓」「盈亏」时必须先调用此工具获取真实数据，不得臆测。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "data_source": {
                "type": "string",
                "description": "行情数据源，用于获取当前价",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO, ROLE_RISK],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "get_my_trades": _spec(
        name="get_my_trades",
        category="account",
        description="获取当前用户的交易记录（买卖流水）。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "symbol": {"type": "string", "description": "可选，按股票代码筛选"},
            "limit": {"type": "integer", "description": "返回条数，默认50", "default": 50},
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "get_orders": _spec(
        name="get_orders",
        category="account",
        description="获取当前账户的委托/订单列表，包括状态、委托价格和成交数量。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "symbol": {"type": "string", "description": "可选，按股票代码筛选"},
            "limit": {"type": "integer", "description": "返回条数，默认50", "default": 50},
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO, ROLE_RISK],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "place_order": _spec(
        name="place_order",
        category="account",
        description="向当前账户提交真实交易委托。用户明确说要下单、买入、卖出时使用。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "symbol": {"type": "string", "description": "股票代码"},
            "side": {"type": "string", "description": "买卖方向", "enum": ["buy", "sell"]},
            "quantity": {"type": "number", "description": "数量（股）"},
            "price": {"type": "number", "description": "限价单价格"},
            "order_type": {"type": "string", "description": "订单类型，当前默认仅支持 limit", "enum": ["limit"], "default": "limit"},
        },
        required=["symbol", "side", "quantity", "price"],
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "cancel_order": _spec(
        name="cancel_order",
        category="account",
        description="撤销当前账户中的某个委托单。若券商暂不支持，会返回明确错误。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "order_id": {"type": "string", "description": "要撤销的订单号"},
            "cancel_all": {"type": "boolean", "description": "是否撤销全部订单，默认 false", "default": False},
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO, ROLE_RISK],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "get_portfolio_summary": _spec(
        name="get_portfolio_summary",
        category="account",
        description="获取当前用户组合总览：总成本、总市值、总浮盈浮亏及各持仓摘要。问「组合怎么样」「总盈亏」时使用。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "data_source": {
                "type": "string",
                "description": "行情数据源",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO, ROLE_RISK],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "set_price_alert": _spec(
        name="set_price_alert",
        category="alert",
        description="设置价格预警。用户说「TSLA 跌超 5% 提醒我」「涨超 10% 提醒」时使用。",
        parameters={
            "symbol": {"type": "string", "description": "股票代码"},
            "rule_type": {
                "type": "string",
                "description": "规则类型：price_change_pct(涨跌幅)、price_vs_ma(与均线)、volume_spike(成交量放量)",
                "enum": ["price_change_pct", "price_vs_ma", "volume_spike"],
                "default": "price_change_pct",
            },
            "threshold_pct": {"type": "number", "description": "涨跌幅阈值，如 -5 表示跌超5%，5 表示涨超5%（仅 rule_type=price_change_pct 时用）"},
            "ma_period": {"type": "integer", "description": "均线周期，如 20（仅 rule_type=price_vs_ma 时用）", "default": 20},
            "above_below": {"type": "string", "description": "above=高于均线提醒，below=低于均线提醒（仅 price_vs_ma）", "enum": ["above", "below"], "default": "below"},
            "volume_multiplier": {"type": "number", "description": "成交量倍数，如 2 表示 2 倍均量时提醒（仅 volume_spike）", "default": 2},
        },
        required=["symbol"],
        roles=[ROLE_GENERAL, ROLE_ALERT, ROLE_RISK],
        requires_auth=True,
        mcp_exposable=True,
    ),
    "list_my_alerts": _spec(
        name="list_my_alerts",
        category="alert",
        description="列出当前用户已设置的所有预警规则。",
        parameters={"symbol": {"type": "string", "description": "可选，按股票代码筛选"}},
        roles=[ROLE_GENERAL, ROLE_ALERT, ROLE_RISK],
        requires_auth=True,
        mcp_exposable=True,
    ),
    "delete_alert": _spec(
        name="delete_alert",
        category="alert",
        description="删除一条预警规则。",
        parameters={"rule_id": {"type": "integer", "description": "规则 ID（从 list_my_alerts 可获得）"}},
        required=["rule_id"],
        roles=[ROLE_GENERAL, ROLE_ALERT, ROLE_RISK],
        requires_auth=True,
        mcp_exposable=True,
    ),
    "save_investment_note": _spec(
        name="save_investment_note",
        category="memory",
        description="将用户的投资笔记或偏好保存到长期记忆，之后问策略、偏好时会自动引用。用户说「保存：对 TSLA 的逻辑是…」「记住我偏好保守」时使用。",
        parameters={
            "content": {"type": "string", "description": "要保存的笔记或偏好内容"},
            "tags": {"type": "string", "description": "可选，逗号分隔标签，如：偏好,风险,TSLA"},
        },
        required=["content"],
        roles=[ROLE_GENERAL],
        requires_auth=True,
        mcp_exposable=True,
    ),
    "get_portfolio_health": _spec(
        name="get_portfolio_health",
        category="account",
        description="对当前用户组合做体检：集中度、浮盈浮亏、趋势/估值标签与简短点评。用户问「体检我的组合」「组合健康吗」时使用。",
        parameters={
            "account_id": {"type": "integer", "description": "可选，指定账户 ID"},
            "provider": {"type": "string", "description": "账户类型：ths, qmt", "enum": ["ths", "qmt"]},
            "data_source": {
                "type": "string",
                "description": "行情数据源",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
        roles=[ROLE_GENERAL, ROLE_PORTFOLIO],
        requires_auth=True,
        account_scoped=True,
        mcp_exposable=True,
    ),
    "search_web": _spec(
        name="search_web",
        category="research",
        description="在网络上搜索信息",
        parameters={
            "query": {"type": "string", "description": "要搜索的查询"},
            "limit": {"type": "integer", "description": "要返回的结果数", "default": 5},
        },
        required=["query"],
        roles=[ROLE_GENERAL, ROLE_RESEARCH],
        mcp_exposable=True,
    ),
    "send_channel_message": _spec(
        name="send_channel_message",
        category="notification",
        description="向当前对话渠道发送一条通知消息。若未指定 channel/chat_id，则默认使用当前会话的渠道和群/会话 ID。",
        parameters={
            "channel": {"type": "string", "description": "渠道类型：telegram 或 feishu，可选；不填则使用当前渠道。", "enum": ["telegram", "feishu"]},
            "chat_id": {"type": "string", "description": "目标 chat_id，可选；不填则使用当前会话绑定的 chat_id。"},
            "text": {"type": "string", "description": "要发送的文本内容。"},
        },
        required=["text"],
        roles=[ROLE_GENERAL],
        requires_auth=True,
        mcp_exposable=False,
    ),
}


def list_internal_tool_specs() -> List[ToolSpec]:
    return list(INTERNAL_TOOL_SPECS.values())


def get_internal_tool_spec(name: str) -> Optional[ToolSpec]:
    return INTERNAL_TOOL_SPECS.get(name)


def bind_tool_handler(name: str, handler: ToolHandler) -> None:
    spec = get_internal_tool_spec(name)
    if spec is None:
        raise KeyError(f"未知内部工具: {name}")
    spec.handler = handler


def get_tool_handler(name: str) -> Optional[ToolHandler]:
    spec = get_internal_tool_spec(name)
    return spec.handler if spec else None


def get_role_tool_names(role: str) -> List[str]:
    return [spec.name for spec in list_internal_tool_specs() if role in spec.roles]


def get_mcp_exposable_tool_specs() -> List[ToolSpec]:
    return [spec for spec in list_internal_tool_specs() if spec.mcp_exposable]


def get_internal_tool_names() -> List[str]:
    return list(INTERNAL_TOOL_SPECS.keys())
