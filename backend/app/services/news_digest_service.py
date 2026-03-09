"""
Phase 6 T6.1: 舆情监控 — 持仓股重大新闻摘要，用于会话内提醒或定时推送。
"""

import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.services.portfolio_service import PositionService
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class NewsDigestService:
    """持仓股舆情：按用户持仓拉取各标的新闻并汇总。"""

    @staticmethod
    async def get_news_for_positions(
        db: Session,
        user_id: int,
        data_source: str = "",
        news_per_symbol: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        获取用户当前持仓标的的新闻摘要。
        返回: [ {"symbol": "AAPL", "news": [{title, source, url, summary, published_at}]}, ... ]
        """
        positions = PositionService.get_positions(db, user_id)
        if not positions:
            return []

        result = []
        for pos in positions:
            symbol = (pos.symbol or "").strip()
            if not symbol:
                continue
            try:
                news = await StockService.get_market_news(
                    db, symbol=symbol, limit=news_per_symbol
                )
                if news:
                    result.append({"symbol": symbol, "news": news})
            except Exception as e:
                logger.warning("舆情拉取失败 %s: %s", symbol, e)
        return result

    @staticmethod
    def format_digest_for_prompt(items: List[Dict[str, Any]], max_items: int = 5) -> str:
        """格式化为可注入 system 的简短文案。"""
        if not items:
            return ""
        lines = ["【持仓股舆情】"]
        count = 0
        for item in items:
            if count >= max_items:
                break
            symbol = item.get("symbol", "")
            news_list = item.get("news") or []
            for n in news_list[:2]:
                title = (n.get("title") or n.get("summary") or "").strip()
                if title:
                    lines.append(f"- {symbol}: {title[:80]}")
                    count += 1
        return "\n".join(lines) if len(lines) > 1 else ""
