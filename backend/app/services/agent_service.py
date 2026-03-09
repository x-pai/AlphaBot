from typing import List, Dict, Any, Optional
import json
from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy.orm import Session
import uuid

from app.models.user import User
from app.services.stock_service import StockService
from app.services.ai_service import AIService
from app.services.llm_registry import LLMRegistry
from app.services.user_service import UserService
from app.middleware.logging import logger
from app.services.search_service import search_service
from app.services.portfolio_service import PositionService, TradeLogService
from app.services.alert_service import AlertService
from app.services.memory_service import MemoryService
from app.services.trade_analysis_service import TradeAnalysisService
from app.core.config import settings
from app.core.registries import ToolRegistry

class AgentTool(BaseModel):
    """智能体工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]

class AgentMessage(BaseModel):
    """智能体消息"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class AgentSession(BaseModel):
    """智能体会话"""
    id: str
    messages: List[AgentMessage]
    user_id: str
    created_at: str
    updated_at: str

class AgentService:
    """AlphaBot智能体服务"""
    
    # 系统提示词
    SYSTEM_PROMPT = """你是AlphaBot，一个专业的股票分析和投资顾问智能体。
你可以帮助用户分析股票，提供市场洞察，并根据用户需求执行各种金融分析任务。

【重要】涉及「我的持仓」「我的盈亏」「我买了/卖了什么」「组合怎么样」时，你必须先调用工具获取真实数据，不得臆测或编造持仓与盈亏。应使用的工具：get_my_positions（持仓与浮盈浮亏）、get_my_trades（交易记录）、get_portfolio_summary（组合总览）、add_trade（记录买卖）。用户问「体检我的组合」时使用 get_portfolio_health。用户说「保存」「记住」投资笔记或偏好时使用 save_investment_note，之后回答策略/偏好问题时会自动引用这些记忆。

你拥有以下核心能力：
1. 股票搜索与筛选：帮助用户找到符合特定条件的股票
2. 技术分析：分析价格趋势、形态和技术指标
3. 基本面分析：解读财务数据、评估公司健康状况和增长前景
4. 新闻分析：提供市场新闻摘要和相关性分析
5. AI预测：基于历史数据和市场情况提供预测
6. 个人持仓与交易：查询持仓、盈亏、交易记录，并帮用户记录买卖（通过 add_trade）

在回答用户问题时，你应该：
1. 分析用户意图，理解他们真正需要什么
2. 使用合适的工具获取必要信息（涉及用户持仓/盈亏时务必先调工具）
3. 基于专业知识和获取的数据提供高质量回答
4. 清晰解释你的分析过程和结论
5. 在不确定时，主动询问澄清问题

记住以下投资原则：
1. 风险管理永远是第一位的
2. 投资决策应该基于数据而非情绪
3. 分散投资是降低风险的重要策略
4. 长期投资通常优于短期投机
5. 市场有效性意味着没有"稳赚不赔"的策略

你需要明确地告知用户，所有分析都是基于历史数据和当前市场情况，不构成投资建议。投资有风险，入市需谨慎。
"""
    
    @staticmethod
    def get_available_tools() -> List[AgentTool]:
        """获取可用工具列表"""
        tools = [
            AgentTool(
                name="search_stocks",
                description="搜索股票信息，通过关键词查找股票",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是股票名称、代码或行业"
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="get_stock_info",
                description="获取股票的详细信息",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码（根据search_stocks工具获取）"
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="get_stock_price_history",
                description="获取股票历史价格数据",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码（根据search_stocks工具获取）"
                    },
                    "interval": {
                        "type": "string",
                        "description": "时间间隔：daily, weekly, monthly",
                        "enum": ["daily", "weekly", "monthly"]
                    },
                    "range": {
                        "type": "string",
                        "description": "时间范围：1m, 3m, 6m, 1y, 5y",
                        "enum": ["1m", "3m", "6m", "1y", "5y"]
                    },
                    "data_source": {
                        "type": "string",
                        "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            # AgentTool(
            #     name="analyze_stock",
            #     description="使用AI分析股票并提供预测",
            #     parameters={
            #         "symbol": {
            #             "type": "string",
            #             "description": "股票代码（根据search_stocks工具获取）"
            #         },
            #         "analysis_mode": {
            #             "type": "string",
            #             "description": "分析类型：基于规则、机器学习或大语言模型",
            #             "enum": ["rule", "ml", "llm"]
            #         },
            #         "data_source": {
            #             "type": "string",
            #             "description": "默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
            #             "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
            #         }
            #     }
            # ),
            AgentTool(
                name="get_market_news",
                description="获取市场新闻和公告",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "相关股票代码，可选（根据search_stocks工具获取）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回新闻条数，默认5条"
                    }
                }
            ),
            AgentTool(
                name="get_stock_fundamentals",
                description="获取股票的基本面数据，包括财务数据、估值指标等",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码（根据search_stocks工具获取）"
                    },
                    "report_type": {
                        "type": "string",
                        "description": "报表类型，all为所有数据",
                        "enum": ["all", "balance_sheet", "income", "cash_flow", "performance", "key_metrics"]
                    },
                    "data_source": {
                        "type": "string",
                        "description": "数据源：tushare, 默认数据源：akshare, 美股数据源：alphavantage, 港股数据源：hk_stock",
                        "enum": ["tushare", "akshare", "alphavantage"]
                    }
                }
            ),
            AgentTool(
                name="get_my_positions",
                description="获取当前用户的持仓列表，含当前价与浮盈浮亏。涉及「我的持仓」「盈亏」时必须先调用此工具获取真实数据，不得臆测。",
                parameters={
                    "data_source": {
                        "type": "string",
                        "description": "行情数据源，用于获取当前价",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="get_my_trades",
                description="获取当前用户的交易记录（买卖流水）。",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "可选，按股票代码筛选"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认50"
                    }
                }
            ),
            AgentTool(
                name="add_trade",
                description="记录一笔买入或卖出，并自动更新持仓。用户说「买了/卖了」「记录买入/卖出」时使用。清仓时若系统提示需确认，请让用户确认后传入 confirm_full_sell=true 再调用一次。",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "side": {
                        "type": "string",
                        "description": "买卖方向",
                        "enum": ["buy", "sell"]
                    },
                    "quantity": {
                        "type": "number",
                        "description": "数量（股）"
                    },
                    "price": {
                        "type": "number",
                        "description": "成交单价"
                    },
                    "fee": {
                        "type": "number",
                        "description": "手续费，可选，默认0"
                    },
                    "confirm_full_sell": {
                        "type": "boolean",
                        "description": "清仓时若系统要求二次确认，用户确认后传 true"
                    }
                }
            ),
            AgentTool(
                name="get_portfolio_summary",
                description="获取当前用户组合总览：总成本、总市值、总浮盈浮亏及各持仓摘要。问「组合怎么样」「总盈亏」时使用。",
                parameters={
                    "data_source": {
                        "type": "string",
                        "description": "行情数据源",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="set_price_alert",
                description="设置价格预警。用户说「TSLA 跌超 5% 提醒我」「涨超 10% 提醒」时使用。",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "股票代码"
                    },
                    "rule_type": {
                        "type": "string",
                        "description": "规则类型：price_change_pct(涨跌幅)、price_vs_ma(与均线)、volume_spike(成交量放量)",
                        "enum": ["price_change_pct", "price_vs_ma", "volume_spike"]
                    },
                    "threshold_pct": {
                        "type": "number",
                        "description": "涨跌幅阈值，如 -5 表示跌超5%，5 表示涨超5%（仅 rule_type=price_change_pct 时用）"
                    },
                    "ma_period": {
                        "type": "integer",
                        "description": "均线周期，如 20（仅 rule_type=price_vs_ma 时用）"
                    },
                    "above_below": {
                        "type": "string",
                        "description": "above=高于均线提醒，below=低于均线提醒（仅 price_vs_ma）",
                        "enum": ["above", "below"]
                    },
                    "volume_multiplier": {
                        "type": "number",
                        "description": "成交量倍数，如 2 表示 2 倍均量时提醒（仅 volume_spike）"
                    }
                }
            ),
            AgentTool(
                name="list_my_alerts",
                description="列出当前用户已设置的所有预警规则。",
                parameters={
                    "symbol": {
                        "type": "string",
                        "description": "可选，按股票代码筛选"
                    }
                }
            ),
            AgentTool(
                name="delete_alert",
                description="删除一条预警规则。",
                parameters={
                    "rule_id": {
                        "type": "integer",
                        "description": "规则 ID（从 list_my_alerts 可获得）"
                    }
                }
            ),
            AgentTool(
                name="save_investment_note",
                description="将用户的投资笔记或偏好保存到长期记忆，之后问策略、偏好时会自动引用。用户说「保存：对 TSLA 的逻辑是…」「记住我偏好保守」时使用。",
                parameters={
                    "content": {
                        "type": "string",
                        "description": "要保存的笔记或偏好内容"
                    },
                    "tags": {
                        "type": "string",
                        "description": "可选，逗号分隔标签，如：偏好,风险,TSLA"
                    }
                }
            ),
            AgentTool(
                name="get_portfolio_health",
                description="对当前用户组合做体检：集中度、浮盈浮亏、趋势/估值标签与简短点评。用户问「体检我的组合」「组合健康吗」时使用。",
                parameters={
                    "data_source": {
                        "type": "string",
                        "description": "行情数据源",
                        "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]
                    }
                }
            ),
            AgentTool(
                name="import_trades",
                description="从 CSV 批量导入交易记录。用户粘贴 CSV 或说「导入交易」时使用。CSV 需含列：日期/date、代码/symbol、方向/side(买/buy/卖/sell)、数量/quantity、价格/price，可选手续费/fee。",
                parameters={
                    "csv": {
                        "type": "string",
                        "description": "CSV 文本内容（含表头一行）"
                    }
                }
            ),
            AgentTool(
                name="run_backtest",
                description="对某只股票做简单回测（买入持有）。用户问「回测一下 XXX 过去一年」时使用。",
                parameters={
                    "symbol": {"type": "string", "description": "股票代码"},
                    "start_date": {"type": "string", "description": "开始日期，如 2023-01-01"},
                    "end_date": {"type": "string", "description": "结束日期，如 2024-01-01"},
                    "data_source": {"type": "string", "description": "数据源", "enum": ["tushare", "akshare", "alphavantage", "hk_stock"]}
                }
            ),
            AgentTool(
                name="get_sim_positions",
                description="获取当前用户的模拟持仓（虚拟资金账户的持仓，非实盘）。",
                parameters={}
            ),
            AgentTool(
                name="add_sim_trade",
                description="模拟交易下单：仅更新虚拟账户，不涉及实盘。用于演练。",
                parameters={
                    "symbol": {"type": "string", "description": "股票代码"},
                    "side": {"type": "string", "description": "buy 或 sell"},
                    "quantity": {"type": "number", "description": "数量"},
                    "price": {"type": "number", "description": "价格"}
                }
            ),
        ]

        # Phase 5 ToolRegistry：仅返回配置启用的工具
        tools = [t for t in tools if ToolRegistry.is_enabled(t.name)]
        
        # 如果搜索API已启用且工具未禁用，添加网络搜索工具
        if settings.SEARCH_API_ENABLED and ToolRegistry.is_enabled("search_web"):
            tools.append(
                AgentTool(
                    name="search_web",
                    description="在网络上搜索信息",
                    parameters={
                        "query": {"type": "string", "description": "要搜索的查询"},
                        "limit": {"type": "integer", "description": "要返回的结果数", "default": 5},
                    }
                )
            )
        return tools
    
    @classmethod
    async def execute_tool(cls, tool_name: str, params: Dict[str, Any], db: Session, user: User) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            # 根据工具名执行对应功能
            if tool_name == "search_stocks":
                results = await StockService.search_stocks(
                    query=params.get("query", ""),
                    data_source=params.get("data_source", ""),
                    db=db
                )
                return {"results": [stock for stock in results]}
            
            elif tool_name == "get_stock_info":
                # search_stocks
                query = params.get("symbol", "")
                query = ''.join(filter(str.isnumeric, query))
                results = await StockService.search_stocks(
                    query=query,
                    data_source=params.get("data_source", ""),
                    db=db
                )
                if not results:
                    return {"error": f"未找到股票: {params.get('symbol', '')}"}
                symbol = results[0].symbol
                stock = await StockService.get_stock_info(
                    symbol=symbol,
                    data_source=params.get("data_source", "")
                )
                if not stock:
                    return {"error": f"未找到股票: {symbol}"}
                # 简化处理：直接返回对象，由后续序列化环节统一处理
                return {"stock": stock}
            
            elif tool_name == "get_stock_price_history":
                # search_stocks
                query = params.get("symbol", "")
                query = ''.join(filter(str.isnumeric, query))
                results = await StockService.search_stocks(
                    query=query,
                    data_source=params.get("data_source", ""),
                    db=db
                )
                if not results:
                    return {"error": f"未找到股票: {params.get('symbol', '')}"}
                symbol = results[0].symbol
                history = await StockService.get_stock_price_history(
                    symbol=symbol,
                    interval=params.get("interval", "daily"),
                    range=params.get("range", "1m"),
                    data_source=params.get("data_source", "")
                )
                if not history:
                    return {"error": f"未找到股票历史数据: {symbol}"}
                return {"history": history.data}
            
            elif tool_name == "analyze_stock":
                # search_stocks
                query = params.get("symbol", "")
                query = ''.join(filter(str.isnumeric, query))
                results = await StockService.search_stocks(
                    query=query,
                    data_source=params.get("data_source", ""),
                    db=db
                )
                if not results:
                    return {"error": f"未找到股票: {params.get('symbol', '')}"}
                symbol = results[0].symbol
                analysis = await AIService.analyze_stock(
                    symbol=symbol,
                    data_source=params.get("data_source", ""),
                    analysis_mode=params.get("analysis_mode", "llm")
                )
                # 记录用户使用
                await UserService.increment_usage(user, db)
                return {"analysis": analysis}
            
            elif tool_name == "get_market_news":
                # search_stocks
                query = params.get("symbol", "")
                query = ''.join(filter(str.isnumeric, query))
                results = await StockService.search_stocks(
                    query=query,
                    data_source=params.get("data_source", ""),
                    db=db
                )
                if not results:
                    return {"error": f"未找到股票: {params.get('symbol', '')}"}
                symbol = results[0].symbol
                news = await StockService.get_market_news(
                    db=db,
                    symbol=symbol,
                    limit=params.get("limit", 5)
                )
                return {"news": news}
            
            elif tool_name == "get_stock_fundamentals":
                # search_stocks
                query = params.get("symbol", "")
                query = ''.join(filter(str.isnumeric, query))
                results = await StockService.search_stocks(
                    query=query,
                    data_source=params.get("data_source", ""),
                    db=db
                )
                if not results:
                    return {"error": f"未找到股票: {params.get('symbol', '')}"}
                symbol = results[0].symbol
                fundamentals = await StockService.get_stock_fundamentals(
                    symbol=symbol,
                    report_type=params.get("report_type", "all"),
                    data_source=params.get("data_source", "")
                )
                return {"fundamentals": fundamentals}

            elif tool_name == "get_my_positions":
                positions = await PositionService.get_positions_with_pnl(
                    db, user.id, params.get("data_source")
                )
                return {"positions": positions}

            elif tool_name == "get_my_trades":
                trades = TradeLogService.list_trades(
                    db,
                    user_id=user.id,
                    symbol=params.get("symbol"),
                    limit=int(params.get("limit") or 50),
                )
                return {
                    "trades": [
                        {
                            "id": t.id,
                            "symbol": t.symbol,
                            "side": t.side,
                            "quantity": t.quantity,
                            "price": t.price,
                            "amount": t.amount,
                            "fee": t.fee or 0,
                            "trade_time": t.trade_time.isoformat() if t.trade_time else None,
                            "source": t.source,
                        }
                        for t in trades
                    ]
                }

            elif tool_name == "add_trade":
                try:
                    symbol = (params.get("symbol") or "").strip().upper()
                    side = (params.get("side") or "buy").lower()
                    quantity = float(params.get("quantity", 0))
                    confirm_full_sell = params.get("confirm_full_sell") is True
                    if side == "sell" and quantity >= 1e-6 and not confirm_full_sell:
                        positions = PositionService.get_positions(db, user.id)
                        pos = next((p for p in positions if (p.symbol or "").upper() == symbol), None)
                        if pos and quantity >= pos.quantity - 1e-6:
                            mem = MemoryService.search(user.id, "割肉 恐慌 清仓", top_k=3)
                            if mem and any((m.get("text") or "").strip() for m in mem):
                                return {
                                    "success": False,
                                    "needs_confirmation": True,
                                    "message": "检测到您过去可能有恐慌割肉/清仓相关记录，是否确认全部卖出？确认后请再次调用 add_trade 并传入 confirm_full_sell=true。",
                                }
                    trade = TradeLogService.add_trade(
                        db,
                        user_id=user.id,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=float(params.get("price", 0)),
                        fee=float(params.get("fee") or 0),
                        source="manual",
                    )
                    out = {
                        "success": True,
                        "message": "已记录交易并更新持仓",
                        "trade": {
                            "id": trade.id,
                            "symbol": trade.symbol,
                            "side": trade.side,
                            "quantity": trade.quantity,
                            "price": trade.price,
                            "amount": trade.amount,
                            "trade_time": trade.trade_time.isoformat() if trade.trade_time else None,
                        },
                    }
                    if side == "buy":
                        mem = MemoryService.search(user.id, "追涨 亏损", top_k=2)
                        if mem and any((m.get("text") or "").strip() for m in mem):
                            out["reminder"] = "根据历史记录您曾有追涨或亏损经历，建议先研究再决策。"
                    return out
                except ValueError as e:
                    return {"success": False, "error": str(e)}

            elif tool_name == "get_portfolio_summary":
                summary = await PositionService.get_portfolio_summary(
                    db, user.id, params.get("data_source")
                )
                return summary

            elif tool_name == "set_price_alert":
                try:
                    symbol = (params.get("symbol") or "").strip()
                    if not symbol:
                        return {"success": False, "error": "请提供股票代码"}
                    rule_type = (params.get("rule_type") or "price_change_pct").strip()
                    params_json = {}
                    if rule_type == "price_change_pct":
                        threshold_pct = params.get("threshold_pct")
                        if threshold_pct is None:
                            return {"success": False, "error": "请提供 threshold_pct，如 -5 表示跌超5%"}
                        params_json["threshold_pct"] = float(threshold_pct)
                    elif rule_type == "price_vs_ma":
                        params_json["ma_period"] = int(params.get("ma_period") or 20)
                        params_json["above_below"] = (params.get("above_below") or "below").lower()
                    elif rule_type == "volume_spike":
                        params_json["multiplier"] = float(params.get("volume_multiplier") or 2)
                    rule = AlertService.create_rule(
                        db, user_id=user.id, symbol=symbol.upper(),
                        rule_type=rule_type, params=params_json
                    )
                    return {
                        "success": True,
                        "message": "预警已设置",
                        "rule": {"id": rule.id, "symbol": rule.symbol, "rule_type": rule.rule_type},
                    }
                except ValueError as e:
                    return {"success": False, "error": str(e)}

            elif tool_name == "list_my_alerts":
                rules = AlertService.list_rules(db, user.id, params.get("symbol"))
                return {
                    "alerts": [
                        {
                            "id": r.id,
                            "symbol": r.symbol,
                            "rule_type": r.rule_type,
                            "params": json.loads(r.params_json) if r.params_json else {},
                            "enabled": r.enabled,
                        }
                        for r in rules
                    ]
                }

            elif tool_name == "delete_alert":
                rule_id = params.get("rule_id")
                if rule_id is None:
                    return {"success": False, "error": "请提供 rule_id"}
                ok = AlertService.delete_rule(db, int(rule_id), user.id)
                return {"success": ok, "message": "已删除" if ok else "规则不存在或无权操作"}

            elif tool_name == "save_investment_note":
                content = (params.get("content") or "").strip()
                if not content:
                    return {"success": False, "error": "请提供要保存的内容"}
                tags_str = params.get("tags") or ""
                tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
                ok = MemoryService.add(user.id, content, tags)
                return {"success": ok, "message": "已保存到长期记忆" if ok else "保存失败，请稍后再试"}

            elif tool_name == "get_portfolio_health":
                health = await PositionService.get_portfolio_health(db, user.id, params.get("data_source"))
                return health

            elif tool_name == "import_trades":
                csv_text = (params.get("csv") or "").strip()
                if not csv_text:
                    return {"success": False, "error": "请提供 CSV 文本内容"}
                try:
                    result = TradeLogService.import_from_csv(
                        db, user_id=user.id, csv_text=csv_text, source="import"
                    )
                    if result.get("imported", 0) > 0:
                        TradeAnalysisService.analyze_and_save_patterns(db, user.id)
                    return result
                except Exception as e:
                    logger.exception("import_trades 失败: %s", e)
                    return {"success": False, "imported": 0, "failed": 0, "errors": [str(e)]}

            elif tool_name == "run_backtest":
                from app.services.backtest_service import BacktestService
                symbol = (params.get("symbol") or "").strip()
                start_date = (params.get("start_date") or "").strip()
                end_date = (params.get("end_date") or "").strip()
                if not symbol or not start_date or not end_date:
                    return {"success": False, "error": "请提供 symbol、start_date、end_date"}
                result = await BacktestService.run(
                    db, symbol, start_date, end_date,
                    data_source=params.get("data_source") or "akshare",
                )
                return result

            elif tool_name == "get_sim_positions":
                from app.services.sim_trade_service import SimTradeService
                positions = SimTradeService.get_positions(db, user.id)
                acc = SimTradeService.get_or_create_account(db, user.id)
                return {
                    "cash_balance": acc.cash_balance,
                    "positions": [
                        {"symbol": p.symbol, "quantity": p.quantity, "cost_price": p.cost_price}
                        for p in positions
                    ],
                }

            elif tool_name == "add_sim_trade":
                from app.services.sim_trade_service import SimTradeService
                symbol = (params.get("symbol") or "").strip()
                side = (params.get("side") or "buy").lower()
                quantity = float(params.get("quantity", 0))
                price = float(params.get("price", 0))
                if not symbol or quantity <= 0 or price <= 0:
                    return {"success": False, "error": "请提供 symbol、quantity、price 且大于 0"}
                return SimTradeService.add_trade(db, user.id, symbol, side, quantity, price)

            elif tool_name == "search_web":
                # 处理Web搜索调用
                query = params.get("query", "")
                limit = params.get("limit", 5)
                
                if not settings.SEARCH_API_ENABLED:
                    return {"error": "搜索API未启用"}
                
                # 执行搜索
                search_results = await search_service.search(query, limit)
                
                # 返回搜索结果
                if search_results.get("success", False):
                    return {
                        "query": query,
                        "results": search_results.get("results", []),
                        "result_count": search_results.get("result_count", 0),
                        "engine": search_results.get("engine", "")
                    }
                else:
                    return {"error": search_results.get("error", "搜索失败")}
            
            else:
                return {"error": f"未知工具: {tool_name}"}
                
        except Exception as e:
            logger.error(f"工具执行错误 {tool_name}: {str(e)}")
            return {"error": f"工具执行错误: {str(e)}"}
    
    @classmethod
    async def _format_tool_result_for_display(cls, tool_name: str, result: Dict[str, Any]) -> str:
        """格式化工具结果显示"""
        try:
            if tool_name == "search_web":
                # 为搜索结果创建Markdown格式
                if "error" in result:
                    return f"搜索错误: {result['error']}"
                
                query = result.get("query", "")
                results = result.get("results", [])
                
                if not results:
                    return f"未找到与{query}相关的搜索结果。"
                
                # 创建Markdown格式的搜索结果
                markdown = f"### 搜索结果：{query}\n\n"
                
                for idx, item in enumerate(results[:3], 1):
                    title = item.get("title", "无标题")
                    link = item.get("link", "#")
                    snippet = item.get("snippet", "无描述")
                    
                    markdown += f"{idx}. **[{title}]({link})**\n"
                    markdown += f"   {snippet}\n\n"
                
                if len(results) > 3:
                    markdown += f"*还有 {len(results) - 3} 条相关结果未显示*\n"
                    
                return markdown
            
            # 处理其他工具的格式化逻辑（允许非JSON对象以字符串形式输出）
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"格式化工具结果出错: {str(e)}")
            return str(result)
            
    @classmethod
    async def process_message(cls, user_message: str, session_id: str, db: Session, user: User, enable_web_search: bool = False, model: Optional[str] = None) -> Dict[str, Any]:
        """处理用户消息"""
        try:
            # 检查是否是特殊命令（例如 "/search 查询内容"）
            if user_message.startswith("/search "):
                # 提取搜索查询
                search_query = user_message[8:].strip()
                if not search_query:
                    return {
                        "content": "请输入要搜索的内容",
                        "session_id": session_id
                    }
                    
                # 执行搜索
                if not settings.SEARCH_API_ENABLED:
                    return {
                        "content": "搜索功能未启用",
                        "session_id": session_id
                    }
                
                search_results = await search_service.search(search_query, 5)
                # 格式化搜索结果
                formatted_result = await cls._format_tool_result_for_display("search_web", {
                    "query": search_query,
                    "results": search_results.get("results", [])
                })
                
                # 保存搜索指令和结果到会话历史
                user_msg = {"role": "user", "content": user_message}
                assistant_msg = {"role": "assistant", "content": f'我搜索了"{search_query}"'}
                messages = [user_msg, assistant_msg]
                cls._save_conversation(session_id, user.id, messages, assistant_msg["content"], db)
                
                return {
                    "content": f'我搜索了"{search_query}"',
                    "session_id": session_id,
                    "tool_outputs": [formatted_result]
                }
            
            # 1. 构建会话历史（传入 user_id 以注入未读预警、舆情/风控/定投提醒）
            extra_system_lines: List[str] = []
            if user.id:
                try:
                    from app.services.news_digest_service import NewsDigestService
                    news_items = await NewsDigestService.get_news_for_positions(db, user.id)
                    if news_items:
                        txt = NewsDigestService.format_digest_for_prompt(news_items, max_items=5)
                        if txt:
                            extra_system_lines.append(txt)
                except Exception as e:
                    logger.debug("舆情摘要注入跳过: %s", e)
                try:
                    from app.services.risk_control_service import RiskControlService
                    summary = await PositionService.get_portfolio_summary(db, user.id, None)
                    total = (summary or {}).get("total_value") or 0
                    positions = await PositionService.get_positions_with_pnl(db, user.id, None)
                    position_values = {}
                    for p in (positions or []):
                        mv = p.get("market_value") or ((p.get("quantity") or 0) * (p.get("current_price") or 0))
                        position_values[p.get("symbol", "") or ""] = mv
                    warnings = RiskControlService.check(db, user.id, portfolio_total=total, position_values=position_values)
                    if warnings:
                        extra_system_lines.append(RiskControlService.format_warnings_for_prompt(warnings))
                except Exception as e:
                    logger.debug("风控提醒注入跳过: %s", e)
                try:
                    from app.models.user_profile import UserProfile
                    from datetime import date
                    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
                    if profile and getattr(profile, "next_dca_date", None) and date.today() >= profile.next_dca_date:
                        extra_system_lines.append("【定投提醒】今日已到或已过计划定投日，可考虑按计划执行定投。")
                except Exception as e:
                    logger.debug("定投提醒注入跳过: %s", e)
            messages = cls._build_messages(user_message, session_id, db, user_id=user.id, extra_system_lines=extra_system_lines or None)

            # 2. 可选：在最后一条用户消息中注入联网搜索提示
            if enable_web_search:
                last_user_message_index = next((i for i in range(len(messages) - 1, -1, -1) if messages[i]["role"] == "user"), -1)
                if last_user_message_index >= 0:
                    original_content = messages[last_user_message_index]["content"]
                    messages[last_user_message_index]["content"] = (
                        f"{original_content}\n\n请优先考虑使用 search_web 工具在网络上搜索必要信息后再作答。"
                    )

            # 3. 迭代式工具调用与回复生成循环
            formatted_results: List[str] = []
            while True:
                llm_client = LLMRegistry.get_client()
                llm_response = await llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    tools=cls.get_available_tools(),
                    tool_choice="auto"
                )

                assistant_message = llm_response.get("choices", [{}])[0].get("message", {})
                tool_calls = assistant_message.get("tool_calls") or []
                print(tool_calls)
                # 如果没有工具调用，则认为是最终回复
                if not tool_calls:
                    content = assistant_message.get("content", "无法生成回复")

                    cls._save_conversation(
                        session_id,
                        user.id,
                        messages,
                        content,
                        db,
                    )

                    return {
                        "content": content,
                        "session_id": session_id,
                        "tool_outputs": formatted_results if formatted_results else None,
                    }

                # 有工具调用：先把包含 tool_calls 的assistant消息加入历史
                messages.append(assistant_message)
                # messages.append({
                #     "role": "assistant",
                #     "content": assistant_message.get("content") or "",
                # })

                # 依次执行工具并把结果追加为tool消息
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    function_name = function.get("name")

                    try:
                        arguments = json.loads(function.get("arguments", "{}"))
                    except Exception as e:
                        logger.error(f"解析工具参数出错: {str(e)}")
                        arguments = {}

                    logger.info(f"执行工具: {function_name}, 参数: {arguments}")
                    tool_result = await cls.execute_tool(function_name, arguments, db, user)

                    # 供前端展示的格式化输出
                    formatted_result = await cls._format_tool_result_for_display(function_name, tool_result)
                    if formatted_result:
                        if function_name == "get_stock_price_history":
                            formatted_results.append(formatted_result[:100])
                        else:
                            formatted_results.append(formatted_result)

                    # 把工具原始结果以tool消息形式追加，供LLM继续推理
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    })
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")
            return {
                "content": f"处理消息时出错: {str(e)}",
                "session_id": session_id,
                "error": str(e)
            }
    
    @classmethod
    def _build_messages(
        cls,
        user_message: str,
        session_id: str,
        db: Session,
        user_id: Optional[int] = None,
        extra_system_lines: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """构建消息历史。若提供 user_id，会在系统消息后插入未读预警（并标记已读）。extra_system_lines 用于 T6.1/T6.4/T6.5 舆情/风控/定投提醒。"""
        from app.models.conversation import Conversation
        from datetime import datetime

        current_datetime = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        system_prompt = cls.SYSTEM_PROMPT + f"\n\n当前日期时间：{current_datetime}"

        if extra_system_lines:
            for line in extra_system_lines:
                if line:
                    system_prompt += "\n\n" + line

        # 长期记忆检索注入（T3.2）：用当前用户消息做 query，将相关记忆注入 system
        if user_id is not None and user_message:
            try:
                memory_results = MemoryService.search(user_id, user_message, top_k=5)
                if memory_results:
                    memory_lines = ["- " + (r.get("text") or "").strip() for r in memory_results if (r.get("text") or "").strip()]
                    if memory_lines:
                        system_prompt += "\n\n以下是与当前对话相关的用户长期记忆（供参考）：\n" + "\n".join(memory_lines)
                # T4.3 相似历史提醒：注入交易模式/亏损相关记忆，便于在类似操作时提示
                pattern_results = MemoryService.search(user_id, "亏损 追涨 割肉 交易模式", top_k=3)
                if pattern_results:
                    pattern_lines = ["- " + (r.get("text") or "").strip() for r in pattern_results if (r.get("text") or "").strip()]
                    if pattern_lines:
                        system_prompt += "\n\n以下为历史交易相关提醒（若与当前操作相关请酌情提示用户）：\n" + "\n".join(pattern_lines)
            except Exception as e:
                logger.warning("长期记忆检索失败: %s", e)

        messages = [{"role": "system", "content": system_prompt}]

        # 会话内插入未读预警（T2.5）
        if user_id is not None:
            unread = AlertService.get_unread_triggers(db, user_id)
            if unread:
                lines = [f"- {t.message}" for t in unread if t.message]
                alert_content = "您有一条新预警：\n" + "\n".join(lines)
                messages.append({"role": "assistant", "content": alert_content})
                AlertService.mark_triggers_read(db, user_id, [t.id for t in unread])

        # 从数据库加载历史消息
        try:
            # 获取最近的10条会话记录作为上下文
            conversations = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).order_by(Conversation.created_at.desc()).limit(10).all()
            
            # 倒序排列，最早的消息在前
            conversations.reverse()
            
            # 添加历史消息，保持对话上下文
            for conv in conversations:
                if conv.user_message:
                    messages.append({"role": "user", "content": conv.user_message})
                if conv.assistant_response:
                    messages.append({"role": "assistant", "content": conv.assistant_response})

                # TODO: 处理工具调用消息
                # 注意：不要把历史的 tool/tool_calls 消息加入到新的对话请求中。
                # OpenAI 要求 `tool` 消息必须紧跟在包含对应 `tool_calls` 的 assistant 消息之后，
                # 否则会触发 400 错误。历史回放的 tool 消息在新的请求上下文中通常无法保持这种严格顺序，
                # 因此这里明确跳过存档的 tool/tool_calls 历史，避免无效的消息序列。

                # 如果有工具调用记录，也添加到消息历史中
                if conv.tool_calls:
                    try:
                        tool_calls_data = json.loads(conv.tool_calls)
                        for tool_call in tool_calls_data:
                            messages.append(tool_call)
                    except:
                        # 如果解析失败，忽略这条工具调用记录
                        pass
                        
        except Exception as e:
            logger.error(f"加载会话历史出错: {str(e)}")
            # 如果出错，仅使用系统提示和当前用户消息
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    @classmethod
    def _save_conversation(cls, session_id: str, user_id: int, messages: List[Dict[str, Any]], 
                         assistant_response: str, db: Session) -> None:
        """保存会话历史"""
        from app.models.conversation import Conversation
        from datetime import datetime
        
        try:
            # 提取本轮用户消息（取最后一条 user 角色消息）
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            # 提取工具调用
            tool_calls = [
                msg for msg in messages 
                if msg.get("role") == "tool" or msg.get("tool_calls") is not None
            ]
            
            # 创建新的会话记录
            conversation = Conversation(
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                created_at=datetime.now()
            )
            
            # 保存到数据库
            db.add(conversation)
            db.commit()
            
        except Exception as e:
            logger.error(f"保存会话历史出错: {str(e)}")
            db.rollback()

    async def get_agent_tools(self):
        """获取代理可用的工具列表"""
        tools = []
        
        # 添加搜索工具（如果启用）
        if settings.SEARCH_API_ENABLED:
            search_tool = {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "在网络上搜索信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "要搜索的查询"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "要返回的结果数",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
            tools.append(search_tool)
            
        # 添加其他工具...
        
        return tools
    
    async def process_agent_tools(self, tool_calls):
        """处理代理工具调用"""
        responses = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            function_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
            
            if function_name == "search_web":
                # 处理Web搜索调用
                query = function_args.get("query")
                limit = function_args.get("limit", 5)
                
                try:
                    # 执行搜索
                    search_results = await search_service.search(query, limit)
                    
                    # 格式化结果为代理可读的格式
                    if search_results.get("success", False):
                        results_formatted = []
                        for result in search_results.get("results", []):
                            results_formatted.append({
                                "title": result.get("title", ""),
                                "link": result.get("link", ""),
                                "snippet": result.get("snippet", ""),
                                "source": result.get("source", "")
                            })
                        
                        # 返回Markdown格式的结果，便于前端解析
                        markdown_response = f"""我从网络上找到了以下与"{query}"相关的信息：
                        
```json
{json.dumps({"query": query, "results": results_formatted}, ensure_ascii=False, indent=2)}
```

以下是结果的摘要：
"""
                        
                        # 为每个结果添加简要描述
                        for idx, result in enumerate(results_formatted[:3], 1):
                            markdown_response += f"\n{idx}. **{result['title']}** - {result['snippet'][:100]}...\n"
                            
                        if len(results_formatted) > 3:
                            markdown_response += f"\n还有 {len(results_formatted) - 3} 个更多结果。"
                        
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": markdown_response
                        }
                    else:
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": f"搜索失败：{search_results.get('error', '未知错误')}"
                        }
                except Exception as e:
                    logger.error(f"处理搜索工具调用错误: {str(e)}")
                    response = {
                        "tool_call_id": tool_call.get("id"),
                        "output": f"处理搜索请求时发生错误: {str(e)}"
                    }
                
                responses.append(response)
            else:
                # 处理现有工具调用
                try:
                    # 执行工具，复用现有的execute_tool方法
                    result = await self.execute_tool(function_name, function_args, None, None)
                    
                    # 格式化结果
                    if "error" in result:
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": f"工具执行错误: {result['error']}"
                        }
                    else:
                        # 将结果转为JSON字符串
                        response = {
                            "tool_call_id": tool_call.get("id"),
                            "output": json.dumps(result, ensure_ascii=False)
                        }
                    
                    responses.append(response)
                except Exception as e:
                    logger.error(f"处理工具调用 {function_name} 错误: {str(e)}")
                    responses.append({
                        "tool_call_id": tool_call.get("id"),
                        "output": f"处理工具调用时发生错误: {str(e)}"
                    })
            
        return responses 