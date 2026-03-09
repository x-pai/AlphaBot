"""
Phase 1 个人数据底座 测试

ROADMAP: T1.1 数据表 | T1.2 PositionService/TradeLogService | T1.3 REST API
验收：get_positions_with_pnl 返回持仓+浮盈浮亏；POST/GET /user/positions、/user/trades 可用
"""
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.portfolio import Position, TradeLog
from app.services.portfolio_service import PositionService, TradeLogService


class TestPositionService:
    """T1.2 PositionService：持仓 CRUD 与 get_positions_with_pnl"""

    def test_set_position_create(self, db, test_user):
        """直接设置持仓：无则创建"""
        pos = PositionService.set_position(
            db,
            user_id=test_user.id,
            symbol="AAPL",
            quantity=100.0,
            cost_price=150.0,
            source="manual",
        )
        db.commit()
        assert pos is not None
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100.0
        assert pos.cost_price == 150.0

    def test_get_positions(self, db, test_user):
        """获取用户全部持仓"""
        PositionService.set_position(
            db, user_id=test_user.id, symbol="TSLA", quantity=50.0, cost_price=200.0
        )
        db.commit()
        rows = PositionService.get_positions(db, test_user.id)
        assert len(rows) >= 1
        assert any(p.symbol == "TSLA" for p in rows)

    @pytest.mark.asyncio
    async def test_get_positions_with_pnl(self, db, test_user):
        """get_positions_with_pnl 返回含 current_price / unrealized_pnl 的列表"""
        PositionService.set_position(
            db, user_id=test_user.id, symbol="MSFT", quantity=10.0, cost_price=300.0
        )
        db.commit()

        with patch(
            "app.services.stock_service.StockService.get_stock_info",
            new_callable=AsyncMock,
            return_value=MagicMock(price=320.0),
        ):
            rows = await PositionService.get_positions_with_pnl(db, test_user.id)
        assert len(rows) >= 1
        msft = next((r for r in rows if r["symbol"] == "MSFT"), None)
        assert msft is not None
        assert msft["current_price"] == 320.0
        assert msft["unrealized_pnl"] is not None
        assert msft["unrealized_pnl"] == pytest.approx(200.0, abs=1e-2)


class TestTradeLogService:
    """T1.2 TradeLogService：add_trade 并同步持仓"""

    def test_add_trade_buy(self, db, test_user):
        """记录买入并更新持仓"""
        trade = TradeLogService.add_trade(
            db,
            user_id=test_user.id,
            symbol="GOOG",
            side="buy",
            quantity=20.0,
            price=140.0,
            source="manual",
        )
        assert trade.side == "buy"
        assert trade.quantity == 20.0
        assert trade.amount == 2800.0
        positions = PositionService.get_positions(db, test_user.id)
        assert any(p.symbol == "GOOG" and p.quantity == 20.0 for p in positions)

    def test_add_trade_sell_reduces_position(self, db, test_user):
        """记录卖出减少持仓"""
        TradeLogService.add_trade(
            db, user_id=test_user.id, symbol="NVDA", side="buy", quantity=10.0, price=500.0
        )
        TradeLogService.add_trade(
            db, user_id=test_user.id, symbol="NVDA", side="sell", quantity=4.0, price=510.0
        )
        positions = PositionService.get_positions(db, test_user.id)
        nvda = next((p for p in positions if p.symbol == "NVDA"), None)
        assert nvda is not None
        assert nvda.quantity == pytest.approx(6.0, abs=1e-6)

    def test_list_trades(self, db, test_user):
        """list_trades 按用户返回交易记录"""
        TradeLogService.add_trade(
            db, user_id=test_user.id, symbol="META", side="buy", quantity=5.0, price=350.0
        )
        trades = TradeLogService.list_trades(db, user_id=test_user.id)
        assert any(t.symbol == "META" for t in trades)


# ---------- REST API 验收 T1.3 ----------
class TestUserPositionsAPI:
    """GET/POST /api/v1/user/positions"""

    def test_get_positions_requires_auth(self, client):
        """未认证时 401"""
        r = client.get("/api/v1/user/positions")
        assert r.status_code == 401

    def test_get_positions_ok(self, client, auth_headers, test_user, db):
        """已认证时返回 200 与 data 数组"""
        PositionService.set_position(
            db, user_id=test_user.id, symbol="API1", quantity=1.0, cost_price=1.0
        )
        db.commit()
        r = client.get("/api/v1/user/positions", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_post_positions_ok(self, client, auth_headers, test_user):
        """POST 直接录入持仓"""
        r = client.post(
            "/api/v1/user/positions",
            headers=auth_headers,
            json={
                "symbol": "POST1",
                "quantity": 100.0,
                "cost_price": 50.0,
                "source": "manual",
            },
        )
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert r.json().get("data", {}).get("symbol") == "POST1"


class TestUserTradesAPI:
    """GET/POST /api/v1/user/trades"""

    def test_post_trades_add_trade(self, client, auth_headers, test_user):
        """POST 记录买卖并更新持仓"""
        r = client.post(
            "/api/v1/user/trades",
            headers=auth_headers,
            json={
                "symbol": "TRADE1",
                "side": "buy",
                "quantity": 30.0,
                "price": 20.0,
                "fee": 0,
                "source": "manual",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("symbol") == "TRADE1"
        assert data.get("data", {}).get("side") == "buy"

    def test_get_trades_ok(self, client, auth_headers):
        """GET 返回交易列表"""
        r = client.get("/api/v1/user/trades", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert isinstance(r.json().get("data"), list)


class TestPortfolioSummaryAndHealth:
    """GET /api/v1/user/portfolio/summary 与 /portfolio/health（T1 + T3.4）"""

    def test_portfolio_summary_ok(self, client, auth_headers):
        """组合总览返回 total_cost、positions 等"""
        r = client.get("/api/v1/user/portfolio/summary", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        d = data.get("data", {})
        assert "total_cost" in d
        assert "positions" in d
        assert "positions_count" in d

    def test_portfolio_health_ok(self, client, auth_headers):
        """组合体检返回 labels、comment"""
        r = client.get("/api/v1/user/portfolio/health", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        d = data.get("data", {})
        assert "labels" in d
        assert "comment" in d
