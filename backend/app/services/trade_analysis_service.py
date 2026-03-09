"""
交易模式分析（T4.2）：基于 TradeLog 识别高频短线、单股亏损等，写入向量记忆供 T4.3/T4.4/T4.5 使用。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.portfolio import TradeLog
from app.services.portfolio_service import TradeLogService
from app.services.memory_service import MemoryService

logger = logging.getLogger("uvicorn")


class TradeAnalysisService:
    """分析用户交易记录并写入长期记忆（交易模式、亏损经历等）。"""

    @staticmethod
    def analyze_and_save_patterns(db: Session, user_id: int) -> List[str]:
        """
        分析 user_id 的交易流水，识别模式并写入 MemoryService。
        返回本次写入的记忆摘要列表。
        """
        trades = TradeLogService.list_trades(db, user_id=user_id, limit=500)
        if not trades:
            return []

        # 按时间升序
        trades = sorted(trades, key=lambda t: t.trade_time or datetime.min)
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(days=90)
        recent_trades = [t for t in trades if (t.trade_time or datetime.min) >= recent_cutoff]

        written: List[str] = []

        # 1) 近期交易频繁 -> 短线
        if len(recent_trades) >= 15:
            msg = "近期交易较频繁，偏短线操作，可注意控制频率与成本。"
            if MemoryService.add(user_id, msg, ["交易模式", "短线"]):
                written.append(msg)

        # 2) 按标的模拟持仓与已实现盈亏
        pos: Dict[str, float] = defaultdict(float)  # symbol -> quantity
        cost: Dict[str, float] = defaultdict(float)  # symbol -> total cost
        realized_pnl: Dict[str, float] = defaultdict(float)
        sell_count: Dict[str, int] = defaultdict(int)

        for t in trades:
            q = t.quantity
            p = t.price
            s = t.symbol
            if t.side == "buy":
                pos[s] += q
                cost[s] += q * p
            else:
                sell_count[s] += 1
                if pos[s] <= 1e-9:
                    continue
                avg_cost = cost[s] / pos[s] if pos[s] else 0
                sell_q = min(q, pos[s])
                realized_pnl[s] += sell_q * (p - avg_cost)
                cost[s] -= sell_q * avg_cost
                pos[s] -= sell_q

        # 3) 单股历史净亏损 -> 写入记忆
        for symbol, pnl in realized_pnl.items():
            if pnl < -1e-6:  # 净亏损
                msg = f"对 {symbol} 历史交易净亏损约 {abs(pnl):.0f}，后续操作可更谨慎。"
                if MemoryService.add(user_id, msg, ["交易模式", "亏损", symbol]):
                    written.append(msg)

        # 4) 某标的多次买卖（可能追涨杀跌）
        for symbol, cnt in sell_count.items():
            if cnt >= 3:
                msg = f"对 {symbol} 曾多次买卖，注意避免追涨杀跌。"
                if MemoryService.add(user_id, msg, ["交易模式", "追涨", symbol]):
                    written.append(msg)

        return written