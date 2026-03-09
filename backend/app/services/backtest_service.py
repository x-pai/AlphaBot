"""
Phase 6 T6.2: 策略回测 — 简单规则回测（如买入持有）在历史行情上的收益。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class BacktestService:
    """简单规则回测：给定标的与区间，计算策略收益。"""

    @staticmethod
    async def run(
        db: Session,
        symbol: str,
        start_date: str,
        end_date: str,
        data_source: str = "akshare",
        rule: str = "buy_and_hold",
    ) -> Dict[str, Any]:
        """
        运行回测。rule 目前仅支持 buy_and_hold。
        返回: total_return_pct, annualized_return_pct, start_price, end_price, days, equity_curve(可选)
        """
        # 数据源多支持 range 为 1m/3m/1y/5y，先拉 5y 再按日期过滤
        history = await StockService.get_stock_price_history(
            symbol=symbol,
            interval="daily",
            range="5y",
            data_source=data_source,
        )
        if not history or not getattr(history, "data", None):
            return {
                "success": False,
                "error": f"无法获取 {symbol} 历史行情",
            }

        data = history.data if hasattr(history, "data") else []
        if isinstance(data, dict):
            data = data.get("prices") or data.get("history") or []
        if not data:
            return {"success": False, "error": "无历史数据"}

        # 取 date 与 close，过滤到 [start_date, end_date]
        start_s = start_date.replace("-", "")[:8]
        end_s = end_date.replace("-", "")[:8]
        points: List[tuple] = []
        for row in data:
            d = getattr(row, "date", None) if not isinstance(row, dict) else (row.get("date") or row.get("Date"))
            c = getattr(row, "close", None) if not isinstance(row, dict) else (row.get("close") or row.get("Close") or row.get("c"))
            if d is None or c is None:
                continue
            ds = str(d).replace("-", "")[:8]
            if start_s <= ds <= end_s:
                points.append((ds, float(c)))
        points.sort(key=lambda x: x[0])
        closes = [p[1] for p in points]
        if len(closes) < 2:
            return {"success": False, "error": "数据点不足"}

        start_price = closes[0]
        end_price = closes[-1]
        total_return_pct = (end_price - start_price) / start_price * 100.0
        days = len(closes)
        years = max(days / 365.0, 1e-6)
        annualized = ((end_price / start_price) ** (1 / years) - 1) * 100.0

        return {
            "success": True,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "rule": rule,
            "start_price": round(start_price, 4),
            "end_price": round(end_price, 4),
            "total_return_pct": round(total_return_pct, 2),
            "annualized_return_pct": round(annualized, 2),
            "days": days,
        }
