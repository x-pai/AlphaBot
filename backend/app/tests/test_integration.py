"""
整体集成测试：应用启动、路由挂载、健康检查、认证与关键 API 串联。

运行方式：在 backend 目录下
  python -m pytest app/tests/test_integration.py -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.core.config import settings


def get_test_db():
    """使用与 conftest 一致的测试库，确保有表与测试用户"""
    from app.tests.conftest import get_test_db as _get
    yield from _get()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = get_test_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_headers(client):
    """依赖 conftest 的 test_user：先创建用户再拿 token"""
    from app.tests.conftest import TEST_USERNAME, TEST_INVITE_CODE
    from app.models.user import User, InviteCode
    from app.services.user_service import UserService
    from app.tests.conftest import TestSessionLocal, TEST_ENGINE
    from app.tests.conftest import Base
    # 确保表存在
    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestSessionLocal()
    try:
        invite = db.query(InviteCode).filter(InviteCode.code == TEST_INVITE_CODE).first()
        if not invite:
            invite = InviteCode(code=TEST_INVITE_CODE, used=False)
            db.add(invite)
            db.flush()
        user = db.query(User).filter(User.username == TEST_USERNAME).first()
        if not user:
            user = User(
                username=TEST_USERNAME,
                email="test@alphabot.test",
                hashed_password=UserService.get_password_hash("testpass"),
                points=2000,
            )
            db.add(user)
            db.flush()
            invite.used = True
            invite.used_by = user.id
        db.commit()
        token = UserService.create_access_token({"sub": user.username})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


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

    def test_user_positions_with_auth(self, client, auth_headers):
        r = client.get(f"{settings.API_V1_STR}/user/positions", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        assert "data" in body

    def test_user_portfolio_summary_with_auth(self, client, auth_headers):
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

    def test_user_risk_warnings_with_auth(self, client, auth_headers):
        r = client.get(f"{settings.API_V1_STR}/user/risk-warnings", headers=auth_headers)
        assert r.status_code == 200
        assert r.json().get("success") is True
