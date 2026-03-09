"""
Skill 定义静态表：统一维护 Agent 工具的元数据（名称、说明、参数 JSON Schema 等）。

注意：
- 这里只负责「定义」，不直接绑定底层实现；
- 实现仍由 AgentService.execute_tool 负责调用各 Service；
- ToolRegistry / 配置负责控制哪些 Skill 对外可见。
"""

from typing import Any, Dict, List


SkillDefinition = Dict[str, Any]


SKILL_DEFINITIONS: List[SkillDefinition] = [
    {
        "name": "search_stocks",
        "category": "research",
        "description": "搜索股票信息，通过关键词查找股票",
        "parameters": {
            "query": {
                "type": "string",
                "description": "搜索关键词，可以是股票名称、代码或行业",
            },
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
    },
    {
        "name": "get_stock_info",
        "category": "research",
        "description": "获取股票的详细信息",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "股票代码（根据search_stocks工具获取）",
            },
            "data_source": {
                "type": "string",
                "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
    },
    {
        "name": "get_stock_price_history",
        "category": "research",
        "description": "获取股票历史价格数据",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "股票代码（根据search_stocks工具获取）",
            },
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
    },
    {
        "name": "get_market_news",
        "category": "research",
        "description": "获取市场新闻和公告",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "相关股票代码，可选（根据search_stocks工具获取）",
            },
            "limit": {
                "type": "integer",
                "description": "返回新闻条数，默认5条",
            },
        },
    },
    {
        "name": "get_stock_fundamentals",
        "category": "research",
        "description": "获取股票的基本面数据，包括财务数据、估值指标等",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "股票代码（根据search_stocks工具获取）",
            },
            "report_type": {
                "type": "string",
                "description": "报表类型，all为所有数据",
                "enum": [
                    "all",
                    "balance_sheet",
                    "income",
                    "cash_flow",
                    "performance",
                    "key_metrics",
                ],
            },
            "data_source": {
                "type": "string",
                "description": "数据源：tushare, 默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                "enum": ["tushare", "akshare", "alphavantage"],
            },
        },
    },
    {
        "name": "get_my_positions",
        "category": "account",
        "description": "获取当前用户的持仓列表，含当前价与浮盈浮亏。涉及「我的持仓」「盈亏」时必须先调用此工具获取真实数据，不得臆测。",
        "parameters": {
            "data_source": {
                "type": "string",
                "description": "行情数据源，用于获取当前价",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            }
        },
    },
    {
        "name": "get_my_trades",
        "category": "account",
        "description": "获取当前用户的交易记录（买卖流水）。",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "可选，按股票代码筛选",
            },
            "limit": {
                "type": "integer",
                "description": "返回条数，默认50",
            },
        },
    },
    {
        "name": "add_trade",
        "category": "account",
        "description": "记录一笔买入或卖出，并自动更新持仓。用户说「买了/卖了」「记录买入/卖出」时使用。清仓时若系统提示需确认，请让用户确认后传入 confirm_full_sell=true 再调用一次。",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "股票代码",
            },
            "side": {
                "type": "string",
                "description": "买卖方向",
                "enum": ["buy", "sell"],
            },
            "quantity": {
                "type": "number",
                "description": "数量（股）",
            },
            "price": {
                "type": "number",
                "description": "成交单价",
            },
            "fee": {
                "type": "number",
                "description": "手续费，可选，默认0",
            },
            "confirm_full_sell": {
                "type": "boolean",
                "description": "清仓时若系统要求二次确认，用户确认后传 true",
            },
        },
    },
    {
        "name": "get_portfolio_summary",
        "category": "account",
        "description": "获取当前用户组合总览：总成本、总市值、总浮盈浮亏及各持仓摘要。问「组合怎么样」「总盈亏」时使用。",
        "parameters": {
            "data_source": {
                "type": "string",
                "description": "行情数据源",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            }
        },
    },
    {
        "name": "set_price_alert",
        "category": "alert",
        "description": "设置价格预警。用户说「TSLA 跌超 5% 提醒我」「涨超 10% 提醒」时使用。",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "股票代码",
            },
            "rule_type": {
                "type": "string",
                "description": "规则类型：price_change_pct(涨跌幅)、price_vs_ma(与均线)、volume_spike(成交量放量)",
                "enum": ["price_change_pct", "price_vs_ma", "volume_spike"],
            },
            "threshold_pct": {
                "type": "number",
                "description": "涨跌幅阈值，如 -5 表示跌超5%，5 表示涨超5%（仅 rule_type=price_change_pct 时用）",
            },
            "ma_period": {
                "type": "integer",
                "description": "均线周期，如 20（仅 rule_type=price_vs_ma 时用）",
            },
            "above_below": {
                "type": "string",
                "description": "above=高于均线提醒，below=低于均线提醒（仅 price_vs_ma）",
                "enum": ["above", "below"],
            },
            "volume_multiplier": {
                "type": "number",
                "description": "成交量倍数，如 2 表示 2 倍均量时提醒（仅 volume_spike）",
            },
        },
    },
    {
        "name": "list_my_alerts",
        "category": "alert",
        "description": "列出当前用户已设置的所有预警规则。",
        "parameters": {
            "symbol": {
                "type": "string",
                "description": "可选，按股票代码筛选",
            }
        },
    },
    {
        "name": "delete_alert",
        "category": "alert",
        "description": "删除一条预警规则。",
        "parameters": {
            "rule_id": {
                "type": "integer",
                "description": "规则 ID（从 list_my_alerts 可获得）",
            }
        },
    },
    {
        "name": "save_investment_note",
        "category": "memory",
        "description": "将用户的投资笔记或偏好保存到长期记忆，之后问策略、偏好时会自动引用。用户说「保存：对 TSLA 的逻辑是…」「记住我偏好保守」时使用。",
        "parameters": {
            "content": {
                "type": "string",
                "description": "要保存的笔记或偏好内容",
            },
            "tags": {
                "type": "string",
                "description": "可选，逗号分隔标签，如：偏好,风险,TSLA",
            },
        },
    },
    {
        "name": "get_portfolio_health",
        "category": "account",
        "description": "对当前用户组合做体检：集中度、浮盈浮亏、趋势/估值标签与简短点评。用户问「体检我的组合」「组合健康吗」时使用。",
        "parameters": {
            "data_source": {
                "type": "string",
                "description": "行情数据源",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            }
        },
    },
    {
        "name": "import_trades",
        "category": "account",
        "description": "从 CSV 批量导入交易记录。用户粘贴 CSV 或说「导入交易」时使用。CSV 需含列：日期/date、代码/symbol、方向/side(买/buy/卖/sell)、数量/quantity、价格/price，可选手续费/fee。",
        "parameters": {
            "csv": {
                "type": "string",
                "description": "CSV 文本内容（含表头一行）",
            }
        },
    },
    {
        "name": "run_backtest",
        "category": "analysis",
        "description": "对某只股票做简单回测（买入持有）。用户问「回测一下 XXX 过去一年」时使用。",
        "parameters": {
            "symbol": {"type": "string", "description": "股票代码"},
            "start_date": {"type": "string", "description": "开始日期，如 2023-01-01"},
            "end_date": {"type": "string", "description": "结束日期，如 2024-01-01"},
            "data_source": {
                "type": "string",
                "description": "数据源",
                "enum": ["tushare", "akshare", "alphavantage", "hk_stock"],
            },
        },
    },
    {
        "name": "get_sim_positions",
        "category": "simulation",
        "description": "获取当前用户的模拟持仓（虚拟资金账户的持仓，非实盘）。",
        "parameters": {},
    },
    {
        "name": "add_sim_trade",
        "category": "simulation",
        "description": "模拟交易下单：仅更新虚拟账户，不涉及实盘。用于演练。",
        "parameters": {
            "symbol": {"type": "string", "description": "股票代码"},
            "side": {"type": "string", "description": "buy 或 sell"},
            "quantity": {"type": "number", "description": "数量"},
            "price": {"type": "number", "description": "价格"},
        },
    },
    {
        "name": "search_web",
        "category": "research",
        "description": "在网络上搜索信息",
        "parameters": {
            "query": {"type": "string", "description": "要搜索的查询"},
            "limit": {
                "type": "integer",
                "description": "要返回的结果数",
                "default": 5,
            },
        },
    },
    {
        "name": "send_channel_message",
        "category": "notification",
        "description": "向当前对话渠道发送一条通知消息。若未指定 channel/chat_id，则默认使用当前会话的渠道和群/会话 ID。",
        "parameters": {
            "channel": {
                "type": "string",
                "description": "渠道类型：telegram 或 feishu，可选；不填则使用当前渠道。",
                "enum": ["telegram", "feishu"],
            },
            "chat_id": {
                "type": "string",
                "description": "目标 chat_id，可选；不填则使用当前会话绑定的 chat_id。",
            },
            "text": {
                "type": "string",
                "description": "要发送的文本内容。",
            },
        },
    },
]

