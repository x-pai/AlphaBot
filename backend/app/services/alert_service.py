"""
预警服务：规则 CRUD、条件引擎、全量评估、未读提醒

规则类型：
- price_change_pct: params_json {"threshold_pct": -5} 跌超5%；{"threshold_pct": 5} 涨超5%
- price_vs_ma: params_json {"ma_period": 20, "above_below": "below"} 价格低于20日均线
- volume_spike: params_json {"multiplier": 2} 成交量大于均量2倍
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.alert import AlertRule, AlertTrigger

logger = logging.getLogger("uvicorn")


class AlertService:
    """预警规则与触发"""

    RULE_TYPES = ("price_change_pct", "price_vs_ma", "volume_spike")

    MAX_RULES_PER_USER = 20

    @staticmethod
    def create_rule(
        db: Session,
        *,
        user_id: int,
        symbol: str,
        rule_type: str,
        params: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> AlertRule:
        if rule_type not in AlertService.RULE_TYPES:
            raise ValueError(f"rule_type 必须是 {AlertService.RULE_TYPES} 之一")
        count = db.query(AlertRule).filter(AlertRule.user_id == user_id).count()
        if count >= AlertService.MAX_RULES_PER_USER:
            raise ValueError(f"每用户最多设置 {AlertService.MAX_RULES_PER_USER} 条预警规则")
        rule = AlertRule(
            user_id=user_id,
            symbol=symbol.strip().upper(),
            rule_type=rule_type,
            params_json=json.dumps(params or {}),
            enabled=enabled,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    @staticmethod
    def list_rules(db: Session, user_id: int, symbol: Optional[str] = None) -> List[AlertRule]:
        q = db.query(AlertRule).filter(AlertRule.user_id == user_id)
        if symbol:
            q = q.filter(AlertRule.symbol == symbol.strip().upper())
        return q.order_by(AlertRule.created_at.desc()).all()

    @staticmethod
    def get_rule(db: Session, rule_id: int, user_id: int) -> Optional[AlertRule]:
        return (
            db.query(AlertRule)
            .filter(AlertRule.id == rule_id, AlertRule.user_id == user_id)
            .first()
        )

    @staticmethod
    def delete_rule(db: Session, rule_id: int, user_id: int) -> bool:
        r = AlertService.get_rule(db, rule_id, user_id)
        if not r:
            return False
        db.delete(r)
        db.commit()
        return True

    @staticmethod
    def set_rule_enabled(db: Session, rule_id: int, user_id: int, enabled: bool) -> bool:
        r = AlertService.get_rule(db, rule_id, user_id)
        if not r:
            return False
        r.enabled = enabled
        db.commit()
        return True

    @staticmethod
    def _triggered_today_for_rule(db: Session, rule_id: int) -> bool:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            db.query(AlertTrigger)
            .filter(
                AlertTrigger.alert_rule_id == rule_id,
                AlertTrigger.triggered_at >= today_start,
            )
            .limit(1)
            .first()
            is not None
        )

    @staticmethod
    async def _get_market_snapshot(symbol: str, data_source: Optional[str] = None) -> Dict[str, Any]:
        """获取当前价、涨跌幅、近期 K 线（用于 MA/成交量）。"""
        from app.services.stock_service import StockService

        out: Dict[str, Any] = {
            "symbol": symbol,
            "price": None,
            "change_percent": None,
            "volume": None,
            "history": [],
        }
        try:
            info = await StockService.get_stock_info(symbol, data_source)
            if info:
                out["price"] = getattr(info, "price", None)
                out["change_percent"] = getattr(info, "changePercent", None)
                if out["change_percent"] is None and hasattr(info, "change_percent"):
                    out["change_percent"] = getattr(info, "change_percent", None)
        except Exception as e:
            logger.warning("get_stock_info %s: %s", symbol, e)
        try:
            hist = await StockService.get_stock_price_history(symbol, "daily", "1m", data_source)
            if hist and getattr(hist, "data", None):
                out["history"] = [
                    {
                        "date": getattr(p, "date", None),
                        "open": getattr(p, "open", None),
                        "high": getattr(p, "high", None),
                        "low": getattr(p, "low", None),
                        "close": getattr(p, "close", None),
                        "volume": getattr(p, "volume", None),
                    }
                    for p in hist.data[-60:]
                ]
                if out["history"] and out["volume"] is None:
                    out["volume"] = out["history"][-1].get("volume")
        except Exception as e:
            logger.warning("get_stock_price_history %s: %s", symbol, e)
        return out

    @staticmethod
    def _evaluate_rule(rule: AlertRule, snapshot: Dict[str, Any]) -> Optional[str]:
        """单条规则是否触发，若触发返回提示文案，否则返回 None。"""
        params = {}
        if rule.params_json:
            try:
                params = json.loads(rule.params_json)
            except Exception:
                pass
        price = snapshot.get("price")
        change_pct = snapshot.get("change_percent")
        history = snapshot.get("history") or []
        volume = snapshot.get("volume")

        if rule.rule_type == "price_change_pct":
            if change_pct is None:
                return None
            threshold = params.get("threshold_pct", -5)
            if threshold < 0 and change_pct <= threshold:
                return f"{rule.symbol} 跌超 {abs(threshold)}%，当前涨跌幅 {change_pct}%"
            if threshold > 0 and change_pct >= threshold:
                return f"{rule.symbol} 涨超 {threshold}%，当前涨跌幅 {change_pct}%"
            return None

        if rule.rule_type == "price_vs_ma":
            if not history or price is None:
                return None
            ma_period = int(params.get("ma_period", 20))
            closes = [h["close"] for h in history if h.get("close") is not None][-ma_period:]
            if len(closes) < ma_period:
                return None
            ma = sum(closes) / len(closes)
            above_below = (params.get("above_below") or "below").lower()
            if above_below == "below" and price < ma:
                return f"{rule.symbol} 价格 {price} 低于 {ma_period} 日均线 {ma:.2f}"
            if above_below == "above" and price > ma:
                return f"{rule.symbol} 价格 {price} 高于 {ma_period} 日均线 {ma:.2f}"
            return None

        if rule.rule_type == "volume_spike":
            if not history or volume is None:
                return None
            multiplier = float(params.get("multiplier", 2))
            vols = [h["volume"] for h in history if h.get("volume") is not None][-20:]
            if not vols:
                return None
            avg_vol = sum(vols) / len(vols)
            if avg_vol <= 0:
                return None
            if volume >= multiplier * avg_vol:
                return f"{rule.symbol} 成交量放量，当前约为 {volume/avg_vol:.1f} 倍均量"
            return None

        return None

    @staticmethod
    async def evaluate_all_rules(db: Session, data_source: Optional[str] = None) -> List[AlertTrigger]:
        """评估所有已启用规则，写入触发记录（同一规则同一自然日仅一条）。"""
        rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()
        if not rules:
            return []
        created: List[AlertTrigger] = []
        rules_by_id: Dict[int, AlertRule] = {r.id: r for r in rules}
        # 按 symbol 聚合，避免同一标的重复拉行情
        by_symbol: Dict[str, List[AlertRule]] = {}
        for r in rules:
            by_symbol.setdefault(r.symbol, []).append(r)
        for symbol, symbol_rules in by_symbol.items():
            snapshot = await AlertService._get_market_snapshot(symbol, data_source)
            for rule in symbol_rules:
                if AlertService._triggered_today_for_rule(db, rule.id):
                    continue
                message = AlertService._evaluate_rule(rule, snapshot)
                if not message:
                    continue
                trigger = AlertTrigger(
                    alert_rule_id=rule.id,
                    user_id=rule.user_id,
                    symbol=rule.symbol,
                    message=message,
                    is_read=False,
                )
                db.add(trigger)
                created.append(trigger)
        if created:
            db.commit()
            for t in created:
                db.refresh(t)

            # 主动通知：根据规则中的 notify_channel 信息，将预警消息下发到对应渠道
            from app.services.notification_service import notify_alert

            for t in created:
                rule = rules_by_id.get(t.alert_rule_id)
                if rule:
                    await notify_alert(rule, t)
        return created

    @staticmethod
    def get_unread_triggers(db: Session, user_id: int) -> List[AlertTrigger]:
        return (
            db.query(AlertTrigger)
            .filter(AlertTrigger.user_id == user_id, AlertTrigger.is_read == False)
            .order_by(AlertTrigger.triggered_at.desc())
            .all()
        )

    @staticmethod
    def mark_triggers_read(db: Session, user_id: int, trigger_ids: Optional[List[int]] = None) -> int:
        q = db.query(AlertTrigger).filter(AlertTrigger.user_id == user_id)
        if trigger_ids is not None:
            q = q.filter(AlertTrigger.id.in_(trigger_ids))
        count = q.update({"is_read": True}, synchronize_session=False)
        db.commit()
        return count
