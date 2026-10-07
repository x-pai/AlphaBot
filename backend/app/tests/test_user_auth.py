from datetime import datetime, timedelta

import pytest
from jose import jwt
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, logger, settings
from app.db.session import get_db
from app.main import app
from app.services.user_service import UserService


@pytest.fixture
def auth_client(client, db, test_user):
    # Use the same session as test_user; the shared SQLite test connection is transactional.
    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield client, test_user, db
    finally:
        app.dependency_overrides[get_db] = previous


@pytest.mark.parametrize("value", [None, "", " " * 32])
def test_secret_key_must_come_from_configuration(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("key", ["a-random-test-only-key-that-is-at-least-32-characters", "too-short"])
def test_configured_secret_key_takes_precedence(monkeypatch, caplog, key):
    monkeypatch.setenv("SECRET_KEY", key)
    with caplog.at_level("WARNING", logger=logger.name):
        assert Settings(_env_file=None).SECRET_KEY.get_secret_value() == key
    assert ("JWTs can be forged" in caplog.text) == (key == "too-short")
    assert key not in caplog.text


def test_example_key_is_loaded_from_configuration(monkeypatch, caplog):
    monkeypatch.setenv("SECRET_KEY", "your-secret-key-for-production")
    with caplog.at_level("WARNING", logger=logger.name):
        configured = Settings(_env_file=None)
    assert configured.SECRET_KEY.get_secret_value() == "your-secret-key-for-production"
    assert "JWTs can be forged" in caplog.text
    assert "your-secret-key-for-production" not in caplog.text


def test_rotating_configured_key_invalidates_existing_token(auth_client, monkeypatch):
    client, test_user, _ = auth_client
    old_token = UserService.create_access_token({"sub": test_user.username})
    monkeypatch.setattr(settings, "SECRET_KEY", SecretStr("different-test-only-jwt-key-for-rotation-0123456789"))

    assert client.get("/api/v1/user/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    new_token = UserService.create_access_token({"sub": test_user.username})
    assert client.get("/api/v1/user/admin/mcp-tokens", headers={"Authorization": f"Bearer {new_token}"}).status_code == 403


def test_login_token_uses_configured_key(auth_client):
    client, test_user, db = auth_client
    test_user.email = "test@example.com"
    db.flush()
    response = client.post(
        "/api/v1/user/token",
        data={"username": test_user.username, "password": "testpass"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=["HS256"])["sub"] == test_user.username

    response = client.get("/api/v1/user/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json().get("success") is True, response.json()
    assert response.json()["data"]["username"] == test_user.username


@pytest.mark.parametrize("key", ["your-secret-key", "a-different-key"])
def test_old_or_wrong_key_cannot_impersonate(auth_client, key):
    client, test_user, _ = auth_client
    token = jwt.encode(
        {"sub": test_user.username, "exp": datetime.utcnow() + timedelta(hours=1)},
        key,
        algorithm="HS256",
    )
    response = client.get("/api/v1/user/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_admin_access_uses_database_role(auth_client):
    client, test_user, db = auth_client
    headers = {"Authorization": f"Bearer {UserService.create_access_token({'sub': test_user.username, 'is_admin': True})}"}
    assert client.get("/api/v1/user/admin/mcp-tokens", headers=headers).status_code == 403

    test_user.is_admin = True
    db.commit()
    assert client.get("/api/v1/user/admin/mcp-tokens", headers=headers).status_code == 200
