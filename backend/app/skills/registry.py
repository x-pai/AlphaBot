from typing import Any, Awaitable, Callable, Dict, Optional
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.middleware.logging import logger
from app.models.user import User
from app.services.alert_service import AlertService
from app.services.ai_service import AIService
from app.services.search_service import search_service
from app.services.stock_service import StockService
from app.services.user_service import UserService
from app.services.notification_service import send_channel_message
from app.services.account import AccountService
from app.skills.definitions import bind_tool_handler, get_tool_handler

SkillHandler = Callable[[Dict[str, Any], Session, User], Awaitable[Dict[str, Any]]]


class SkillRegistry:
    @classmethod
    def get_handler(cls, name: str) -> Optional[SkillHandler]:
        return get_tool_handler(name)


def internal_tool_handler(name: str) -> Callable[[SkillHandler], SkillHandler]:
    def _decorator(func: SkillHandler) -> SkillHandler:
        bind_tool_handler(name, func)
        return func
    return _decorator


@internal_tool_handler("get_my_positions")
async def _handle_get_my_positions(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    positions = await AccountService.get_positions_with_pnl(
        db,
        user.id,
        params.get("data_source"),
        account_id=params.get("account_id"),
        provider=params.get("provider"),
    )
    return {"positions": positions}


@internal_tool_handler("get_my_trades")
async def _handle_get_my_trades(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    trades = AccountService.list_trades(
        db,
        user.id,
        symbol=params.get("symbol"),
        limit=int(params.get("limit") or 50),
        account_id=params.get("account_id"),
        provider=params.get("provider"),
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


@internal_tool_handler("get_orders")
async def _handle_get_orders(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    try:
        orders = AccountService.get_orders(
            db,
            user.id,
            symbol=params.get("symbol"),
            limit=int(params.get("limit") or 50),
            account_id=params.get("account_id"),
            provider=params.get("provider"),
        )
        return {
            "orders": [
                {
                    "id": getattr(order, "id", None),
                    "order_id": getattr(order, "order_id", None),
                    "symbol": order.symbol,
                    "name": getattr(order, "name", None),
                    "side": order.side,
                    "quantity": order.quantity,
                    "filled_quantity": getattr(order, "filled_quantity", 0.0),
                    "price": order.price,
                    "status": getattr(order, "status", ""),
                    "order_type": getattr(order, "order_type", "limit"),
                    "order_time": order.order_time.isoformat() if getattr(order, "order_time", None) else None,
                    "source": getattr(order, "source", "broker"),
                }
                for order in orders
            ]
        }
    except (ValueError, NotImplementedError) as e:
        return {"success": False, "error": str(e)}


@internal_tool_handler("place_order")
async def _handle_place_order(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    try:
        order = AccountService.place_order(
            db,
            user.id,
            symbol=(params.get("symbol") or "").strip().upper(),
            side=(params.get("side") or "buy").lower(),
            quantity=float(params.get("quantity", 0)),
            price=float(params.get("price", 0)),
            order_type=(params.get("order_type") or "limit").lower(),
            account_id=params.get("account_id"),
            provider=params.get("provider"),
        )
        return {
            "success": True,
            "message": "委托已提交",
            "order": {
                "order_id": getattr(order, "order_id", None),
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
                "status": getattr(order, "status", "submitted"),
                "order_time": order.order_time.isoformat() if getattr(order, "order_time", None) else None,
            },
        }
    except (ValueError, NotImplementedError) as e:
        return {"success": False, "error": str(e)}


@internal_tool_handler("cancel_order")
async def _handle_cancel_order(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    try:
        result = AccountService.cancel_order(
            db,
            user.id,
            order_id=params.get("order_id"),
            cancel_all=bool(params.get("cancel_all", False)),
            account_id=params.get("account_id"),
            provider=params.get("provider"),
        )
        if isinstance(result, dict):
            return {"success": True, **result}
        return {"success": True, "result": result}
    except (ValueError, NotImplementedError) as e:
        return {"success": False, "error": str(e)}


@internal_tool_handler("get_portfolio_summary")
async def _handle_get_portfolio_summary(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    summary = await AccountService.get_portfolio_summary(
        db,
        user.id,
        params.get("data_source"),
        account_id=params.get("account_id"),
        provider=params.get("provider"),
    )
    return summary


@internal_tool_handler("set_price_alert")
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


@internal_tool_handler("list_my_alerts")
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


@internal_tool_handler("delete_alert")
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


@internal_tool_handler("save_investment_note")
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


@internal_tool_handler("get_portfolio_health")
async def _handle_get_portfolio_health(
    params: Dict[str, Any],
    db: Session,
    user: User,
) -> Dict[str, Any]:
    health = await AccountService.get_portfolio_health(
        db,
        user.id,
        params.get("data_source"),
        account_id=params.get("account_id"),
        provider=params.get("provider"),
    )
    return health


@internal_tool_handler("search_stocks")
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


@internal_tool_handler("get_stock_info")
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


@internal_tool_handler("get_stock_price_history")
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


@internal_tool_handler("get_stock_intraday")
async def _handle_get_stock_intraday(
    params: Dict[str, Any],
    db: Session,  # noqa: ARG001
    user: User,  # noqa: ARG001
) -> Dict[str, Any]:
    symbol = (params.get("symbol") or "").strip().upper()
    if not symbol:
        return {"error": "请提供股票代码"}
    intraday = await StockService.get_stock_intraday(
        symbol=symbol,
        refresh=bool(params.get("refresh", False)),
        data_source=params.get("data_source", ""),
    )
    if not intraday:
        return {"error": f"未找到股票分时数据: {symbol}"}
    return {"intraday": intraday}


@internal_tool_handler("get_market_news")
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


@internal_tool_handler("get_stock_fundamentals")
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


@internal_tool_handler("search_web")
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


@internal_tool_handler("send_channel_message")
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
