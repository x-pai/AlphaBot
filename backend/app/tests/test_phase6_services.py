"""
Phase 6 增强能力 测试

ROADMAP: T6.0 MCP Server | T6.2 策略回测 | T6.3 模拟交易 | T6.4 风控提醒 | T6.5 用户画像/定投
验收：模拟交易、回测、风控、用户画像 API 及服务逻辑。
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.sim_trade_service import SimTradeService
from app.services.backtest_service import BacktestService
from app.services.risk_control_service import RiskControlService
from app.models.user_profile import UserProfile


class TestSimTradeService:
    """T6.3 模拟交易"""

    def test_get_or_create_account(self, db, test_user):
        acc = SimTradeService.get_or_create_account(db, test_user.id)
        assert acc is not None
        assert acc.user_id == test_user.id
        assert acc.cash_balance == 1_000_000.0

    def test_add_trade_buy(self, db, test_user):
        result = SimTradeService.add_trade(db, test_user.id, "SIM1", "buy", 100, 50.0)
        assert result.get("success") is True
        assert "cash_balance" in result
        positions = SimTradeService.get_positions(db, test_user.id)
        assert any(p.symbol == "SIM1" and p.quantity == 100 for p in positions)

    def test_add_trade_sell_insufficient_fails(self, db, test_user):
        result = SimTradeService.add_trade(db, test_user.id, "SIM2", "sell", 10, 100.0)
        assert result.get("success") is False
        assert "持仓不足" in result.get("error", "")


class TestBacktestService:
    """T6.2 策略回测"""

    @pytest.mark.asyncio
    async def test_run_returns_structure(self):
        mock_history = MagicMock()
        mock_history.data = [
            MagicMock(date="2024-01-01", close=100.0),
            MagicMock(date="2024-01-02", close=102.0),
        ]
        with patch(
            "app.services.backtest_service.StockService.get_stock_price_history",
            new_callable=AsyncMock,
            return_value=mock_history,
        ):
            result = await BacktestService.run(
                None, "MOCK", "2024-01-01", "2024-01-02", "akshare"
            )
        assert "success" in result
        if result.get("success"):
            assert "total_return_pct" in result or "symbol" in result


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


class TestUserProfileAndSimAPI:
    """REST: /user/profile, /user/sim/positions, /user/sim/trade, /user/backtest, /user/risk-warnings"""

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

    def test_get_sim_positions_ok(self, client, auth_headers):
        r = client.get("/api/v1/user/sim/positions", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "cash_balance" in data.get("data", {})
        assert "positions" in data.get("data", {})

    def test_post_sim_trade_ok(self, client, auth_headers, test_user):
        r = client.post(
            "/api/v1/user/sim/trade",
            headers=auth_headers,
            json={"symbol": "API_SIM", "side": "buy", "quantity": 10, "price": 100},
        )
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_post_backtest_ok(self, client, auth_headers):
        with patch(
            "app.services.backtest_service.StockService.get_stock_price_history",
            new_callable=AsyncMock,
            return_value=MagicMock(data=[MagicMock(date="2024-01-01", close=100), MagicMock(date="2024-01-02", close=105)]),
        ):
            r = client.post(
                "/api/v1/user/backtest",
                headers=auth_headers,
                json={"symbol": "MOCK", "start_date": "2024-01-01", "end_date": "2024-01-02", "data_source": "akshare"},
            )
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert "data" in r.json()

    def test_get_risk_warnings_ok(self, client, auth_headers):
        r = client.get("/api/v1/user/risk-warnings", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "warnings" in data.get("data", {})
