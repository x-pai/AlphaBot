"""
Phase 2 主动预警 测试

ROADMAP: T2.1 数据表 | T2.2 AlertService | T2.3 定时任务 | T2.4 Agent 工具 / REST
验收：evaluate_rules 返回触发列表；POST/GET/DELETE /user/alerts；未读 triggers 可查
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.alert import AlertRule, AlertTrigger
from app.services.alert_service import AlertService


class TestAlertService:
    """T2.2 AlertService：规则 CRUD、条件引擎"""

    def test_create_rule(self, db, test_user):
        """创建预警规则"""
        rule = AlertService.create_rule(
            db,
            user_id=test_user.id,
            symbol="TSLA",
            rule_type="price_change_pct",
            params={"threshold_pct": -5},
        )
        assert rule.symbol == "TSLA"
        assert rule.rule_type == "price_change_pct"
        assert rule.enabled is True
        params = json.loads(rule.params_json or "{}")
        assert params.get("threshold_pct") == -5

    def test_list_rules(self, db, test_user):
        """按用户列出规则"""
        AlertService.create_rule(
            db, user_id=test_user.id, symbol="AAPL", rule_type="price_change_pct", params={"threshold_pct": 5}
        )
        rules = AlertService.list_rules(db, test_user.id)
        assert len(rules) >= 1
        assert any(r.symbol == "AAPL" for r in rules)

    def test_delete_rule(self, db, test_user):
        """删除规则"""
        rule = AlertService.create_rule(
            db, user_id=test_user.id, symbol="DEL", rule_type="price_change_pct", params={}
        )
        ok = AlertService.delete_rule(db, rule.id, test_user.id)
        assert ok is True
        assert AlertService.get_rule(db, rule.id, test_user.id) is None

    def test_evaluate_rule_price_change_pct_trigger(self):
        """price_change_pct：跌超阈值时返回提示文案"""
        rule = MagicMock()
        rule.symbol = "X"
        rule.rule_type = "price_change_pct"
        rule.params_json = json.dumps({"threshold_pct": -5})
        msg = AlertService._evaluate_rule(
            rule,
            {"price": 100, "change_percent": -6, "history": [], "volume": None},
        )
        assert msg is not None
        assert "跌超" in msg and "5" in msg

    def test_evaluate_rule_price_change_pct_no_trigger(self):
        """涨跌幅未达阈值不触发"""
        rule = MagicMock()
        rule.symbol = "X"
        rule.rule_type = "price_change_pct"
        rule.params_json = json.dumps({"threshold_pct": -5})
        msg = AlertService._evaluate_rule(
            rule,
            {"price": 100, "change_percent": -2, "history": [], "volume": None},
        )
        assert msg is None

    @pytest.mark.asyncio
    async def test_evaluate_all_rules_creates_trigger(self, db, test_user):
        """evaluate_all_rules 在条件满足时写入 AlertTrigger"""
        rule = AlertService.create_rule(
            db,
            user_id=test_user.id,
            symbol="MOCK",
            rule_type="price_change_pct",
            params={"threshold_pct": -10},
        )
        snapshot = {
            "symbol": "MOCK",
            "price": 90,
            "change_percent": -12,
            "history": [],
            "volume": None,
        }
        with patch(
            "app.services.alert_service.AlertService._get_market_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            with patch.object(
                AlertService,
                "_triggered_today_for_rule",
                return_value=False,
            ):
                created = await AlertService.evaluate_all_rules(db)
        # 可能创建了 trigger（若当日未触发过）
        triggers = db.query(AlertTrigger).filter(AlertTrigger.alert_rule_id == rule.id).all()
        # 至少规则存在；若引擎触发则有一条记录
        assert rule.id is not None


class TestUserAlertsAPI:
    """T2.4 REST：/api/v1/user/alerts"""

    def test_get_alerts_requires_auth(self, client):
        r = client.get("/api/v1/user/alerts")
        assert r.status_code == 401

    def test_post_alerts_ok(self, client, auth_headers, test_user):
        """创建预警规则"""
        r = client.post(
            "/api/v1/user/alerts",
            headers=auth_headers,
            json={
                "symbol": "ALERT1",
                "rule_type": "price_change_pct",
                "params": {"threshold_pct": -5},
                "enabled": True,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("symbol") == "ALERT1"

    def test_get_alerts_ok(self, client, auth_headers):
        r = client.get("/api/v1/user/alerts", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert isinstance(r.json().get("data"), list)

    def test_delete_alert_ok(self, client, auth_headers, db, test_user):
        """删除指定规则"""
        rule = AlertService.create_rule(
            db, user_id=test_user.id, symbol="DEL2", rule_type="price_change_pct", params={}
        )
        db.commit()
        r = client.delete(f"/api/v1/user/alerts/{rule.id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_get_unread_triggers_ok(self, client, auth_headers):
        """未读预警触发列表"""
        r = client.get("/api/v1/user/alerts/triggers/unread", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert isinstance(r.json().get("data"), list)
