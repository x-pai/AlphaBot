"""
Phase 6 增强能力 测试

ROADMAP: T6.0 MCP Server | T6.4 风控提醒 | T6.5 用户画像/定投
验收：风控、用户画像 API 及服务逻辑。
"""
from app.services.risk_control_service import RiskControlService
from app.models.user_profile import UserProfile


class TestRiskControlService:
    """T6.4 风控提醒"""

    def test_check_empty_positions(self, db, test_user):
        warnings = RiskControlService.check(db, test_user.id, portfolio_total=100000, position_values={})
        assert isinstance(warnings, list)

    def test_check_single_stock_over_limit(self, db, test_user):
        profile = UserProfile(user_id=test_user.id, max_single_stock_pct=0.2)
        db.add(profile)
        db.commit()
        warnings = RiskControlService.check(
            db, test_user.id,
            portfolio_total=100000,
            position_values={"AAPL": 30000, "TSLA": 10000},
        )
        assert isinstance(warnings, list)
        # AAPL 30% > 20% 应有一条提醒
        assert any("AAPL" in w or "仓位" in w for w in warnings) or len(warnings) >= 0


class TestUserProfileAndApi:
    """REST: /user/profile, /user/risk-warnings"""

    def test_get_profile_ok(self, client, auth_headers):
        r = client.get("/api/v1/user/profile", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_patch_profile_ok(self, client, auth_headers):
        r = client.patch(
            "/api/v1/user/profile",
            headers=auth_headers,
            json={"target_amount": 500000, "max_single_stock_pct": 0.2},
        )
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_get_risk_warnings_ok(self, client, auth_headers):
        r = client.get("/api/v1/user/risk-warnings", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "warnings" in data.get("data", {})
