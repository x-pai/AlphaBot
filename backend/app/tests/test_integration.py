"""
整体集成测试：应用启动、路由挂载、健康检查、认证与关键 API 串联。

运行方式：在 backend 目录下
  python -m pytest app/tests/test_integration.py -v
"""
from app.core.config import settings


class TestAppIntegration:
    """整体：应用可启动、路由与认证正常"""

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_api_docs_mounted(self, client):
        r = client.get(f"{settings.API_V1_STR}/docs")
        assert r.status_code == 200

    def test_openapi_json_ok(self, client):
        r = client.get(f"{settings.API_V1_STR}/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "openapi" in data
        assert "paths" in data

    def test_user_positions_requires_auth(self, client):
        r = client.get(f"{settings.API_V1_STR}/user/positions")
        assert r.status_code == 401

    def test_user_positions_with_auth(self, client, auth_headers, account_with_empty_positions):
        r = client.get(f"{settings.API_V1_STR}/user/positions", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        assert "data" in body

    def test_user_portfolio_summary_with_auth(self, client, auth_headers, account_with_empty_positions):
        r = client.get(f"{settings.API_V1_STR}/user/portfolio/summary", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_user_profile_with_auth(self, client, auth_headers):
        r = client.get(f"{settings.API_V1_STR}/user/profile", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_user_alerts_with_auth(self, client, auth_headers):
        r = client.get(f"{settings.API_V1_STR}/user/alerts", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_user_risk_warnings_with_auth(self, client, auth_headers, account_with_empty_positions):
        r = client.get(f"{settings.API_V1_STR}/user/risk-warnings", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True
