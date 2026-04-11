from typing import Any, Awaitable, Callable, Dict, Optional
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.middleware.logging import logger
from app.models.user import User
from app.services.alert_service import AlertService
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.services.portfolio_service import PositionService, TradeLogService
from app.services.search_service import search_service
from app.services.stock_service import StockService
from app.services.trade_analysis_service import TradeAnalysisService
from app.services.user_service import UserService
from app.services.backtest_service import BacktestService
from app.services.sim_trade_service import SimTradeService
from app.services.notification_service import send_channel_message

SkillHandler = Callable[[Dict[str, Any], Session, User], Awaitable[Dict[str, Any]]]


class SkillRegistry:
    """
    Skill 执行注册表。

    目前已将账户类 / 预警类 / 记忆类 / 部分研究与回测类工具的实现拆分为独立 handler，
    其余少量内部工具仍由 AgentService.execute_tool 内部处理，逐步迁移。
    """

    _handlers: Dict[str, SkillHandler] = {}

    @classmethod
    def register(cls, name: str, handler: SkillHandler) -> None:
        cls._handlers[name] = handler

    @classmethod
    def get_handler(cls, name: str) -> Optional[SkillHandler]:
        return cls._handlers.get(name)


async def _handle_get_my_positions(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    positions = await PositionService.get_positions_with_pnl(
        db, user.id, params.get("data_source")
    )
    return {"positions": positions}


async def _handle_get_my_trades(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
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


async def _handle_add_trade(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    try:
        symbol = (params.get("symbol") or "").strip().upper()
        side = (params.get("side") or "buy").lower()
        quantity = float(params.get("quantity", 0))
        confirm_full_sell = params.get("confirm_full_sell") is True
        if side == "sell" and quantity >= 1e-6 and not confirm_full_sell:
            positions = PositionService.get_positions(db, user.id)
            pos = next(
                (p for p in positions if (p.symbol or "").upper() == symbol),
                None,
            )
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
        out: Dict[str, Any] = {
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


async def _handle_get_portfolio_summary(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    summary = await PositionService.get_portfolio_summary(
        db,
        user.id,
        params.get("data_source"),
    )
    return summary


async def _handle_set_price_alert(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    try:
        symbol = (params.get("symbol") or "").strip()
        if not symbol:
            return {"success": False, "error": "请提供股票代码"}
        rule_type = (params.get("rule_type") or "price_change_pct").strip()
        params_json: Dict[str, Any] = {}
        if rule_type == "price_change_pct":
            threshold_pct = params.get("threshold_pct")
            if threshold_pct is None:
                return {
                    "success": False,
                    "error": "请提供 threshold_pct，如 -5 表示跌超5%",
                }
            params_json["threshold_pct"] = float(threshold_pct)
        elif rule_type == "price_vs_ma":
            params_json["ma_period"] = int(params.get("ma_period") or 20)
            params_json["above_below"] = (
                params.get("above_below") or "below"
            ).lower()
        elif rule_type == "volume_spike":
            params_json["multiplier"] = float(params.get("volume_multiplier") or 2)

        # 可选：记录通知渠道，用于规则触发时主动下行到 IM 渠道
        notify_channel = params.get("notify_channel")
        if isinstance(notify_channel, dict):
            params_json["notify_channel"] = notify_channel

        rule = AlertService.create_rule(
            db,
            user_id=user.id,
            symbol=symbol.upper(),
            rule_type=rule_type,
            params=params_json,
        )
        return {
            "success": True,
            "message": "预警已设置",
            "rule": {"id": rule.id, "symbol": rule.symbol, "rule_type": rule.rule_type},
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


async def _handle_list_my_alerts(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
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


async def _handle_delete_alert(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    rule_id = params.get("rule_id")
    if rule_id is None:
        return {"success": False, "error": "请提供 rule_id"}
    ok = AlertService.delete_rule(db, int(rule_id), user.id)
    return {"success": ok, "message": "已删除" if ok else "规则不存在或无权操作"}


async def _handle_save_investment_note(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    content = (params.get("content") or "").strip()
    if not content:
        return {"success": False, "error": "请提供要保存的内容"}
    tags_str = params.get("tags") or ""
    tags = (
        [t.strip() for t in tags_str.split(",") if t.strip()]
        if tags_str
        else None
    )
    ok = MemoryService.add(user.id, content, tags)
    return {
        "success": ok,
        "message": "已保存到长期记忆" if ok else "保存失败，请稍后再试",
    }


async def _handle_get_portfolio_health(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    health = await PositionService.get_portfolio_health(
        db,
        user.id,
        params.get("data_source"),
    )
    return health


async def _handle_import_trades(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    csv_text = (params.get("csv") or "").strip()
    if not csv_text:
        return {"success": False, "error": "请提供 CSV 文本内容"}
    try:
        result = TradeLogService.import_from_csv(
            db,
            user_id=user.id,
            csv_text=csv_text,
            source="import",
        )
        if result.get("imported", 0) > 0:
            TradeAnalysisService.analyze_and_save_patterns(db, user.id)
        return result
    except Exception as e:  # noqa: BLE001
        logger.exception("import_trades 失败: %s", e)
        return {
            "success": False,
            "imported": 0,
            "failed": 0,
            "errors": [str(e)],
        }


async def _handle_search_stocks(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    results = await StockService.search_stocks(
        query=params.get("query", ""),
        data_source=params.get("data_source", ""),
        db=db,
    )
    return {"results": [stock for stock in results]}


async def _handle_get_stock_info(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    query = params.get("symbol", "")
    query = "".join(filter(str.isnumeric, query))
    results = await StockService.search_stocks(
        query=query,
        data_source=params.get("data_source", ""),
        db=db,
    )
    if not results:
        return {"error": f"未找到股票: {params.get('symbol', '')}"}
    symbol = results[0].symbol
    stock = await StockService.get_stock_info(
        symbol=symbol,
        data_source=params.get("data_source", ""),
    )
    if not stock:
        return {"error": f"未找到股票: {symbol}"}
    return {"stock": stock}


async def _handle_get_stock_price_history(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    query = params.get("symbol", "")
    query = "".join(filter(str.isnumeric, query))
    results = await StockService.search_stocks(
        query=query,
        data_source=params.get("data_source", ""),
        db=db,
    )
    if not results:
        return {"error": f"未找到股票: {params.get('symbol', '')}"}
    symbol = results[0].symbol
    history = await StockService.get_stock_price_history(
        symbol=symbol,
        interval=params.get("interval", "daily"),
        range=params.get("range", "1m"),
        data_source=params.get("data_source", ""),
    )
    if not history:
        return {"error": f"未找到股票历史数据: {symbol}"}
    return {"history": history.data}


async def _handle_get_market_news(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    query = params.get("symbol", "")
    query = "".join(filter(str.isnumeric, query))
    results = await StockService.search_stocks(
        query=query,
        data_source=params.get("data_source", ""),
        db=db,
    )
    if not results:
        return {"error": f"未找到股票: {params.get('symbol', '')}"}
    symbol = results[0].symbol
    news = await StockService.get_market_news(
        db=db,
        symbol=symbol,
        limit=params.get("limit", 5),
    )
    return {"news": news}


async def _handle_get_stock_fundamentals(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    query = params.get("symbol", "")
    query = "".join(filter(str.isnumeric, query))
    results = await StockService.search_stocks(
        query=query,
        data_source=params.get("data_source", ""),
        db=db,
    )
    if not results:
        return {"error": f"未找到股票: {params.get('symbol', '')}"}
    symbol = results[0].symbol
    fundamentals = await StockService.get_stock_fundamentals(
        symbol=symbol,
        report_type=params.get("report_type", "all"),
        data_source=params.get("data_source", ""),
    )
    return {"fundamentals": fundamentals}


async def _handle_run_backtest(
    params: Dict[str, Any],
    db: Session,
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    symbol = (params.get("symbol") or "").strip()
    start_date = (params.get("start_date") or "").strip()
    end_date = (params.get("end_date") or "").strip()
    if not symbol or not start_date or not end_date:
        return {"success": False, "error": "请提供 symbol、start_date、end_date"}
    result = await BacktestService.run(
        db,
        symbol,
        start_date,
        end_date,
        data_source=params.get("data_source") or "akshare",
    )
    return result


async def _handle_get_sim_positions(
    params: Dict[str, Any],  # noqa: ARG001
    db: Session,
    user: User,
) -> Dict[str, Any]:
    positions = SimTradeService.get_positions(db, user.id)
    acc = SimTradeService.get_or_create_account(db, user.id)
    return {
        "cash_balance": acc.cash_balance,
        "positions": [
            {"symbol": p.symbol, "quantity": p.quantity, "cost_price": p.cost_price}
            for p in positions
        ],
    }


async def _handle_add_sim_trade(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    symbol = (params.get("symbol") or "").strip()
    side = (params.get("side") or "buy").lower()
    quantity = float(params.get("quantity", 0))
    price = float(params.get("price", 0))
    if not symbol or quantity <= 0 or price <= 0:
        return {"success": False, "error": "请提供 symbol、quantity、price 且大于 0"}
    return SimTradeService.add_trade(db, user.id, symbol, side, quantity, price)


async def _handle_search_web(
    params: Dict[str, Any],
    db: Session,  # noqa: ARG001
    user: User,
) -> Dict[str, Any]:
    query = params.get("query", "")
    limit = params.get("limit", 5)

    if not settings.SEARCH_API_ENABLED:
        return {"error": "搜索API未启用"}

    if user.points < 2000:
        return {"error": "联网搜索至少需要 2000 积分"}

    search_results = await search_service.search(query, limit)

    if search_results.get("success", False):
        return {
            "query": query,
            "results": search_results.get("results", []),
            "result_count": search_results.get("result_count", 0),
            "engine": search_results.get("engine", ""),
        }
    return {"error": search_results.get("error", "搜索失败")}


async def _handle_send_channel_message(
    params: Dict[str, Any],
    db: Session,  # noqa: ARG001
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    """
    显式发送渠道消息的 Skill。

    若未提供 channel/chat_id，则期望在上游（AgentService.process_message）注入
    当前会话的渠道与 chat_id。
    """
    text = (params.get("text") or "").strip()
    if not text:
        return {"success": False, "error": "text 不能为空"}

    channel = params.get("channel")
    chat_id = params.get("chat_id")

    if not channel or chat_id is None:
        return {"success": False, "error": "channel 或 chat_id 缺失"}

    result = await send_channel_message(channel, chat_id, text)
    return result


# 注册内置 Skill handler
SkillRegistry.register("get_my_positions", _handle_get_my_positions)
SkillRegistry.register("get_my_trades", _handle_get_my_trades)
SkillRegistry.register("add_trade", _handle_add_trade)
SkillRegistry.register("get_portfolio_summary", _handle_get_portfolio_summary)
SkillRegistry.register("set_price_alert", _handle_set_price_alert)
SkillRegistry.register("list_my_alerts", _handle_list_my_alerts)
SkillRegistry.register("delete_alert", _handle_delete_alert)
SkillRegistry.register("save_investment_note", _handle_save_investment_note)
SkillRegistry.register("get_portfolio_health", _handle_get_portfolio_health)
SkillRegistry.register("import_trades", _handle_import_trades)
SkillRegistry.register("search_stocks", _handle_search_stocks)
SkillRegistry.register("get_stock_info", _handle_get_stock_info)
SkillRegistry.register("get_stock_price_history", _handle_get_stock_price_history)
SkillRegistry.register("get_market_news", _handle_get_market_news)
SkillRegistry.register("get_stock_fundamentals", _handle_get_stock_fundamentals)
SkillRegistry.register("run_backtest", _handle_run_backtest)
SkillRegistry.register("get_sim_positions", _handle_get_sim_positions)
SkillRegistry.register("add_sim_trade", _handle_add_sim_trade)
SkillRegistry.register("search_web", _handle_search_web)
SkillRegistry.register("send_channel_message", _handle_send_channel_message)
