"""
Phase 6 T6.4: 风控提醒 — 单股/行业超限、单日亏损超阈值。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.portfolio import Position, TradeLog
from app.models.user_profile import UserProfile


class RiskControlService:
    """风控检查：仓位集中度、单日亏损等。"""

    @staticmethod
    def get_or_create_profile(db: Session, user_id: int) -> Optional[UserProfile]:
        p = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not p:
            p = UserProfile(user_id=user_id)
            db.add(p)
            db.flush()
        return p

    @staticmethod
    def check(
        db: Session,
        user_id: int,
        portfolio_total: Optional[float] = None,
        position_values: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """
        执行风控检查，返回提醒文案列表。
        portfolio_total: 组合总市值（若未传则用 position_values 求和）
        position_values: symbol -> 当前市值
        """
        warnings: List[str] = []
        if not position_values:
            position_values = {}
        total = portfolio_total
        if total is None:
            total = sum(position_values.values()) or 1.0

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        max_single = getattr(profile, "max_single_stock_pct", None) if profile else None
        if max_single is None:
            max_single = 0.25  # 默认单股上限 25%
        max_daily = getattr(profile, "max_daily_loss_pct", None) if profile else None
        if max_daily is None:
            max_daily = -5.0  # 默认单日亏损超 5% 提醒

        # 单股超限
        for symbol, value in position_values.items():
            if total <= 0:
                continue
            pct = value / total * 100
            if pct >= max_single * 100:
                warnings.append(f"风控提醒：{symbol} 仓位 {pct:.1f}% 超过设定上限 {max_single*100:.0f}%")

        # 单日亏损（从 trade_log 估算当日盈亏，简化：仅提示今日有较大卖出亏损时提醒）
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        day_trades = (
            db.query(TradeLog)
            .filter(
                TradeLog.user_id == user_id,
                TradeLog.trade_time >= today_start,
            )
            .all()
        )
        day_pnl = 0.0
        for t in day_trades:
            if t.side == "sell":
                day_pnl -= t.amount or 0  # 简化：卖出额视为“实现”
            else:
                day_pnl -= t.amount or 0  # 买入为负
        if total > 0 and day_pnl < 0:
            day_pnl_pct = day_pnl / total * 100
            if day_pnl_pct <= max_daily:
                warnings.append(f"风控提醒：今日已实现/浮动亏损约 {day_pnl_pct:.1f}%，超过阈值 {max_daily}%")

        return warnings

    @staticmethod
    def format_warnings_for_prompt(warnings: List[str]) -> str:
        if not warnings:
            return ""
        return "【风控提醒】\n" + "\n".join(f"- {w}" for w in warnings)
