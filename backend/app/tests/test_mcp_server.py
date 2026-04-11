import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

import app.mcp_server as mcp_module
from app.models.user import McpToken, User
from app.services.mcp_token_service import McpTokenService
from app.services.user_service import UserService


@pytest.mark.asyncio
class TestExecuteAuthenticated:
    async def test_execute_tool_success(self):
        db = MagicMock()
        user = MagicMock()
        user.id = 1
        user.can_use_mcp = True
        user.is_unlimited = False
        user.mcp_daily_usage_count = 0
        user.mcp_daily_limit = 50
        db.get.return_value = user

        token_ctx = mcp_module._CURRENT_MCP_USER_ID.set(1)
        try:
            with patch.object(mcp_module, "SessionLocal", return_value=db):
                with patch.object(mcp_module.UsageService, "require_mcp_usage") as m_usage:
                    with patch.object(
                        mcp_module.AgentService,
                        "execute_tool",
                        new_callable=AsyncMock,
                    ) as m_exec:
                        m_exec.return_value = {"ok": True}
                        out = await mcp_module._execute_authenticated("get_my_positions", {})
                        assert out == {"ok": True}
                        m_usage.assert_called_once_with(user, db)
                        m_exec.assert_called_once_with("get_my_positions", {}, db, user)
                db.close.assert_called_once()
        finally:
            mcp_module._CURRENT_MCP_USER_ID.reset(token_ctx)

    async def test_execute_tool_http_error_returns_error_dict(self):
        db = MagicMock()
        user = MagicMock()
        db.get.return_value = user

        token_ctx = mcp_module._CURRENT_MCP_USER_ID.set(1)
        try:
            with patch.object(mcp_module, "SessionLocal", return_value=db):
                with patch.object(
                    mcp_module.UsageService,
                    "require_mcp_usage",
                    side_effect=mcp_module.HTTPException(status_code=403, detail="MCP daily usage limit exceeded"),
                ):
                    out = await mcp_module._execute_authenticated("get_my_positions", {})
                    assert out == {"error": "MCP daily usage limit exceeded"}
                db.close.assert_called_once()
        finally:
            mcp_module._CURRENT_MCP_USER_ID.reset(token_ctx)


class TestBuildMcpApp:
    def test_raises_when_fastmcp_not_installed(self):
        with patch.object(mcp_module, "_HAS_FASTMCP", False):
            with pytest.raises(ImportError, match="请安装 fastmcp"):
                mcp_module._build_mcp_app()

    def test_http_app_has_health_route(self):
        app = mcp_module.build_http_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestMcpTokenRoutes:
    def test_create_list_and_revoke_token(self, authenticated_client, db, test_user):
        client, auth_headers = authenticated_client

        create_resp = client.post(
            "/api/v1/user/mcp-tokens",
            headers=auth_headers,
            json={"name": "Cursor"},
        )
        assert create_resp.status_code == 200
        payload = create_resp.json()
        assert payload["success"] is True
        raw_token = payload["data"]["token"]
        assert raw_token.startswith(McpTokenService.TOKEN_PREFIX)

        list_resp = client.get("/api/v1/user/mcp-tokens", headers=auth_headers)
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert len(list_payload["data"]) == 1
        token_id = list_payload["data"][0]["id"]

        revoke_resp = client.delete(f"/api/v1/user/mcp-tokens/{token_id}", headers=auth_headers)
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["data"]["revoked"] is True

        token_in_db = db.query(McpToken).filter(McpToken.id == token_id).first()
        assert token_in_db is not None
        assert token_in_db.is_active is False

    def test_low_points_user_cannot_create_mcp_token(self, client, db):
        user = User(
            username="lowpoints",
            email="lowpoints@test.local",
            hashed_password=UserService.get_password_hash("pass123"),
            points=150,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = UserService.create_access_token({"sub": user.username})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/api/v1/user/mcp-tokens",
            headers=headers,
            json={"name": "Blocked"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "200 points" in body["error"]


class TestMcpAuthMiddleware:
    def test_mcp_path_requires_bearer(self, db, test_user):
        app = mcp_module.build_http_app()
        with patch.object(mcp_module, "SessionLocal", return_value=db):
            client = TestClient(app)
            response = client.get("/mcp")
            assert response.status_code == 401

    def test_token_authenticate_and_touch(self, db, test_user):
        token, raw_token = McpTokenService.create_token(db, test_user, "Desktop")
        authed = McpTokenService.authenticate_token(db, raw_token)
        assert authed.id == token.id
        McpTokenService.touch_token(db, authed, "127.0.0.1")

        db.refresh(authed)
        assert authed.last_used_ip == "127.0.0.1"
        assert authed.last_used_at is not None
